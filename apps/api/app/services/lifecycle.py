from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AccessRequest,
    ArtifactArchive,
    CostRecord,
    Incident,
    LifecycleJob,
    ProviderAssignment,
    UsageRecord,
)
from app.models.enums import RequestStatus
from app.providers.registry import get_provider_adapter
from app.services.audit import record_audit_event
from app.services.notifications import notify_roles, notify_user
from app.services.policies import ensure_standard_policy
from app.services.state_machine import transition


def assignment_totals(db: Session, assignment_id: str) -> tuple[Decimal, int, datetime | None]:
    total_cost = db.scalar(
        select(func.coalesce(func.sum(CostRecord.amount), 0)).where(
            CostRecord.assignment_id == assignment_id
        )
    )
    total_tokens = db.scalar(
        select(func.coalesce(func.sum(UsageRecord.tokens), 0)).where(
            UsageRecord.assignment_id == assignment_id
        )
    )
    freshness_at = db.scalar(
        select(func.max(CostRecord.freshness_at)).where(CostRecord.assignment_id == assignment_id)
    )
    return Decimal(str(total_cost or 0)), int(total_tokens or 0), freshness_at


def record_usage_and_cost(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    tokens: int,
    request_count: int,
    cost_amount: Decimal,
    correlation_id: str,
) -> str:
    now = datetime.now(UTC)
    db.add(
        UsageRecord(
            assignment_id=assignment.id,
            provider=assignment.provider,
            tokens=tokens,
            request_count=request_count,
            measured_at=now,
            freshness_at=now,
        )
    )
    db.add(
        CostRecord(
            assignment_id=assignment.id,
            provider=assignment.provider,
            amount=cost_amount,
            currency="USD",
            cost_type="estimated",
            freshness_at=now,
        )
    )
    total_cost, _, _ = assignment_totals(db, assignment.id)
    total_cost += cost_amount
    request = db.get(AccessRequest, assignment.request_id)
    if not request:
        raise ValueError("Assignment has no access request")

    percent = int((total_cost / Decimal(request.requested_budget)) * 100)
    threshold = "normal"
    if percent >= 100:
        threshold = "enforcement"
        assignment.status = "suspended"
        request.status = transition(request.status, RequestStatus.SUSPENDED)
        db.add(
            Incident(
                severity="high",
                summary=f"Budget enforcement suspended {assignment.provider} assignment",
                metadata_json={
                    "assignment_id": assignment.id,
                    "request_id": request.id,
                    "budget_percent": percent,
                },
            )
        )
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="access_suspended",
            message=f"{request.project_name} reached its budget limit and was suspended.",
        )
        notify_roles(
            db,
            role_names={"platform_admin"},
            event_type="budget_enforcement",
            message=f"{request.project_name} was suspended at {percent}% of budget.",
        )
    elif percent >= 90:
        threshold = "critical"
        notify_roles(
            db,
            role_names={"platform_admin"},
            event_type="budget_critical",
            message=f"{request.project_name} reached {percent}% of budget.",
        )
    elif percent >= 70:
        threshold = "warning"
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="budget_warning",
            message=f"{request.project_name} reached {percent}% of budget.",
        )

    event = record_audit_event(
        db,
        event_type=f"budget.{threshold}",
        actor_user_id=actor_user_id,
        target_type="provider_assignment",
        target_id=assignment.id,
        request_id=assignment.request_id,
        provider=assignment.provider,
        action="record_usage_and_cost",
        result="success",
        correlation_id=correlation_id,
        metadata_json={
            "tokens": tokens,
            "request_count": request_count,
            "cost_amount": str(cost_amount),
            "total_cost": str(total_cost),
            "budget_percent": percent,
        },
    )
    return event.event_type


def enforce_archive_retention(
    db: Session,
    *,
    actor_user_id: str,
    correlation_id: str,
    job: LifecycleJob,
) -> int:
    now = datetime.now(UTC)
    job.status = "running"
    expired_archives = db.scalars(
        select(ArtifactArchive)
        .where(ArtifactArchive.retention_expires_at <= now)
        .order_by(ArtifactArchive.retention_expires_at.asc())
    ).all()
    purged_count = 0
    for archive in expired_archives:
        if archive.storage_location.startswith("purged://"):
            continue
        original_location = archive.storage_location
        archive.storage_location = f"purged://{archive.id}"
        record_audit_event(
            db,
            event_type="artifact.retention_purged",
            actor_user_id=actor_user_id,
            target_type="artifact_archive",
            target_id=archive.id,
            project_id=archive.project_id,
            action="enforce_archive_retention",
            result="success",
            correlation_id=correlation_id,
            metadata_json={
                "assignment_id": archive.assignment_id,
                "original_location": original_location,
                "checksum": archive.checksum,
                "retention_expires_at": archive.retention_expires_at.isoformat(),
            },
        )
        purged_count += 1

    job.status = "completed"
    job.payload = {**(job.payload or {}), "purged_count": purged_count}
    return purged_count


async def restore_assignment(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    reason: str,
    correlation_id: str,
    job: LifecycleJob | None = None,
) -> str:
    request = db.get(AccessRequest, assignment.request_id)
    if not request:
        raise ValueError("Assignment has no access request")
    if job is None:
        job = LifecycleJob(
            job_type="restore_access",
            status="running",
            attempt_count=1,
            idempotency_key=f"restore:{assignment.id}",
            payload={
                "assignment_id": assignment.id,
                "actor_user_id": actor_user_id,
                "reason": reason,
                "correlation_id": correlation_id,
            },
        )
        db.add(job)
    else:
        job.status = "running"
    adapter = get_provider_adapter(assignment.provider)
    await adapter.restore_access(assignment.id, job.idempotency_key)
    assignment.status = "active"
    if request.status == RequestStatus.SUSPENDED:
        request.status = transition(request.status, RequestStatus.ACTIVE)
    job.status = "completed"
    event = record_audit_event(
        db,
        event_type="provider.restored",
        actor_user_id=actor_user_id,
        target_type="provider_assignment",
        target_id=assignment.id,
        request_id=assignment.request_id,
        provider=assignment.provider,
        action="restore_access",
        result="success",
        reason=reason,
        correlation_id=correlation_id,
    )
    notify_user(
        db,
        user_id=request.requester_id,
        event_type="access_restored",
        message=f"{request.project_name} access was restored.",
    )
    return event.event_type


async def expire_and_archive_assignment(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    reason: str,
    correlation_id: str,
    job: LifecycleJob | None = None,
) -> tuple[str, ArtifactArchive]:
    request = db.get(AccessRequest, assignment.request_id)
    if not request:
        raise ValueError("Assignment has no access request")
    adapter = get_provider_adapter(assignment.provider)

    if request.status == RequestStatus.ACTIVE:
        request.status = transition(request.status, RequestStatus.EXPIRED)
    elif request.status == RequestStatus.SUSPENDED:
        request.status = transition(request.status, RequestStatus.EXPIRED)
    request.expires_at = datetime.now(UTC)
    assignment.expires_at = request.expires_at
    assignment.status = "expired"

    request.status = transition(request.status, RequestStatus.ARCHIVING)
    policy_version = ensure_standard_policy(db)
    artifact_retention_days = int(policy_version.document.get("artifact_retention_days", 365))
    if job is None:
        job = LifecycleJob(
            job_type="archive_and_deprovision",
            status="running",
            attempt_count=1,
            idempotency_key=f"archive:{assignment.id}",
            payload={
                "assignment_id": assignment.id,
                "actor_user_id": actor_user_id,
                "reason": reason,
                "correlation_id": correlation_id,
            },
        )
        db.add(job)
    else:
        job.status = "running"
    db.flush()
    archive_result = await adapter.archive_artifacts(assignment.id, job.idempotency_key)
    archive = ArtifactArchive(
        project_id=assignment.project_id,
        assignment_id=assignment.id,
        storage_provider=archive_result["storage_provider"],
        storage_location=archive_result["storage_location"],
        checksum=archive_result["checksum"],
        retention_expires_at=datetime.now(UTC) + timedelta(days=artifact_retention_days),
        created_by_job_id=job.id,
    )
    db.add(archive)

    await adapter.deprovision_access(assignment.id, f"deprovision:{assignment.id}")
    assignment.status = "deprovisioned"
    request.status = transition(request.status, RequestStatus.CLOSED)
    request.closed_at = datetime.now(UTC)
    job.status = "completed"
    event = record_audit_event(
        db,
        event_type="lifecycle.closed",
        actor_user_id=actor_user_id,
        target_type="provider_assignment",
        target_id=assignment.id,
        request_id=assignment.request_id,
        provider=assignment.provider,
        action="expire_archive_deprovision",
        result="success",
        reason=reason,
        correlation_id=correlation_id,
        metadata_json={"archive_location": archive.storage_location},
    )
    notify_user(
        db,
        user_id=request.requester_id,
        event_type="request_closed",
        message=f"{request.project_name} was archived and closed.",
    )
    notify_roles(
        db,
        role_names={"platform_admin"},
        event_type="lifecycle_closed",
        message=f"{request.project_name} was archived and deprovisioned.",
    )
    return event.event_type, archive

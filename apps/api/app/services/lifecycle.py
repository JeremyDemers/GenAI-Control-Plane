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
    elif percent >= 90:
        threshold = "critical"
    elif percent >= 70:
        threshold = "warning"

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


async def restore_assignment(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    reason: str,
    correlation_id: str,
) -> str:
    request = db.get(AccessRequest, assignment.request_id)
    if not request:
        raise ValueError("Assignment has no access request")
    job = LifecycleJob(
        job_type="restore_access",
        status="running",
        attempt_count=1,
        idempotency_key=f"restore:{assignment.id}",
    )
    db.add(job)
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
    return event.event_type


async def expire_and_archive_assignment(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    reason: str,
    correlation_id: str,
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
    job = LifecycleJob(
        job_type="archive_and_deprovision",
        status="running",
        attempt_count=1,
        idempotency_key=f"archive:{assignment.id}",
    )
    db.add(job)
    db.flush()
    archive_result = await adapter.archive_artifacts(assignment.id, job.idempotency_key)
    archive = ArtifactArchive(
        project_id=assignment.project_id,
        assignment_id=assignment.id,
        storage_provider=archive_result["storage_provider"],
        storage_location=archive_result["storage_location"],
        checksum=archive_result["checksum"],
        retention_expires_at=datetime.now(UTC) + timedelta(days=365),
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
    return event.event_type, archive

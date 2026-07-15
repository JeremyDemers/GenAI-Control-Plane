from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AccessRequest, LifecycleJob, ProviderAssignment
from app.models.enums import RequestStatus
from app.providers.base import ProviderOperationError
from app.providers.registry import get_provider_adapter
from app.services.audit import record_audit_event
from app.services.lifecycle import (
    enforce_archive_retention,
    expire_and_archive_assignment,
    record_usage_and_cost,
    restore_assignment,
    warn_expiring_access,
)
from app.services.notifications import notify_roles, notify_user
from app.services.reports import cost_allocation_csv
from app.services.state_machine import transition

SAFE_PROVIDER_ERROR_KEYS = {"code", "message", "operation", "provider_status", "retry_after"}


def safe_provider_error_details(details: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in details.items() if key in SAFE_PROVIDER_ERROR_KEYS}


def _provision_key(request_id: str, provider: str) -> str:
    return f"provision:{request_id}:{provider}"


def _restore_key(assignment_id: str) -> str:
    return f"restore:{assignment_id}"


def _archive_key(assignment_id: str) -> str:
    return f"archive:{assignment_id}"


def _usage_key(assignment_id: str, correlation_id: str) -> str:
    return f"usage:{assignment_id}:{correlation_id}"


def _retention_key(correlation_id: str) -> str:
    return f"retention:{correlation_id}"


def _expiration_warning_key(correlation_id: str) -> str:
    return f"expiration-warning:{correlation_id}"


def _start_job(job: LifecycleJob) -> None:
    job.status = "running"
    if job.attempt_count == 0:
        job.attempt_count = 1
    job.failure_information = {}


def _fail_job(
    db: Session,
    *,
    job: LifecycleJob,
    message: str,
    operation: str,
    retryable: bool,
    details: dict[str, object] | None = None,
) -> None:
    job.status = "failed"
    job.failure_information = {
        "retryable": retryable,
        "message": message,
        "details": safe_provider_error_details(
            details or {"code": "lifecycle_job_failed", "operation": operation}
        ),
    }
    db.flush()


def enqueue_provisioning_jobs(
    db: Session, request: AccessRequest, correlation_id: str
) -> list[LifecycleJob]:
    if request.status in {RequestStatus.APPROVED, RequestStatus.PROVISIONING_FAILED}:
        request.status = transition(request.status, RequestStatus.PROVISIONING)

    jobs: list[LifecycleJob] = []
    for provider in request.provider_names:
        idempotency_key = _provision_key(request.id, provider)
        job = db.scalar(select(LifecycleJob).where(LifecycleJob.idempotency_key == idempotency_key))
        if job:
            jobs.append(job)
            continue

        job = LifecycleJob(
            job_type="provision_access",
            status="queued",
            attempt_count=0,
            idempotency_key=idempotency_key,
            payload={
                "request_id": request.id,
                "provider": provider,
                "correlation_id": correlation_id,
            },
        )
        db.add(job)
        db.flush()
        jobs.append(job)
        record_audit_event(
            db,
            event_type="lifecycle_job.queued",
            actor_user_id=None,
            target_type="lifecycle_job",
            target_id=job.id,
            request_id=request.id,
            project_id=request.project_id,
            provider=provider,
            action="enqueue_provision_access",
            result="queued",
            correlation_id=correlation_id,
        )
    db.flush()
    return jobs


def enqueue_lifecycle_action_job(
    db: Session,
    *,
    assignment: ProviderAssignment,
    job_type: str,
    actor_user_id: str,
    reason: str,
    correlation_id: str,
) -> LifecycleJob:
    key_by_type = {
        "restore_access": _restore_key,
        "archive_and_deprovision": _archive_key,
    }
    idempotency_key = key_by_type[job_type](assignment.id)
    existing_job = db.scalar(
        select(LifecycleJob).where(LifecycleJob.idempotency_key == idempotency_key)
    )
    if existing_job:
        if existing_job.status == "failed":
            existing_job.status = "queued"
            existing_job.payload = {
                "assignment_id": assignment.id,
                "request_id": assignment.request_id,
                "provider": assignment.provider,
                "actor_user_id": actor_user_id,
                "reason": reason,
                "correlation_id": correlation_id,
            }
            existing_job.failure_information = {}
        return existing_job

    job = LifecycleJob(
        job_type=job_type,
        status="queued",
        attempt_count=0,
        idempotency_key=idempotency_key,
        payload={
            "assignment_id": assignment.id,
            "request_id": assignment.request_id,
            "provider": assignment.provider,
            "actor_user_id": actor_user_id,
            "reason": reason,
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        event_type="lifecycle_job.queued",
        actor_user_id=actor_user_id,
        target_type="lifecycle_job",
        target_id=job.id,
        request_id=assignment.request_id,
        project_id=assignment.project_id,
        provider=assignment.provider,
        action=f"enqueue_{job_type}",
        result="queued",
        reason=reason,
        correlation_id=correlation_id,
    )
    db.flush()
    return job


def enqueue_usage_processing_job(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    tokens: int,
    request_count: int,
    cost_amount: Decimal,
    correlation_id: str,
) -> LifecycleJob:
    idempotency_key = _usage_key(assignment.id, correlation_id)
    existing_job = db.scalar(
        select(LifecycleJob).where(LifecycleJob.idempotency_key == idempotency_key)
    )
    if existing_job:
        return existing_job

    job = LifecycleJob(
        job_type="record_usage_and_cost",
        status="queued",
        attempt_count=0,
        idempotency_key=idempotency_key,
        payload={
            "assignment_id": assignment.id,
            "request_id": assignment.request_id,
            "provider": assignment.provider,
            "actor_user_id": actor_user_id,
            "tokens": tokens,
            "request_count": request_count,
            "cost_amount": str(cost_amount),
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        event_type="lifecycle_job.queued",
        actor_user_id=actor_user_id,
        target_type="lifecycle_job",
        target_id=job.id,
        request_id=assignment.request_id,
        project_id=assignment.project_id,
        provider=assignment.provider,
        action="enqueue_record_usage_and_cost",
        result="queued",
        correlation_id=correlation_id,
    )
    db.flush()
    return job


def enqueue_archive_retention_job(
    db: Session,
    *,
    actor_user_id: str,
    correlation_id: str,
) -> LifecycleJob:
    idempotency_key = _retention_key(correlation_id)
    existing_job = db.scalar(
        select(LifecycleJob).where(LifecycleJob.idempotency_key == idempotency_key)
    )
    if existing_job:
        return existing_job

    job = LifecycleJob(
        job_type="enforce_archive_retention",
        status="queued",
        attempt_count=0,
        idempotency_key=idempotency_key,
        payload={"actor_user_id": actor_user_id, "correlation_id": correlation_id},
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        event_type="lifecycle_job.queued",
        actor_user_id=actor_user_id,
        target_type="lifecycle_job",
        target_id=job.id,
        action="enqueue_enforce_archive_retention",
        result="queued",
        correlation_id=correlation_id,
    )
    db.flush()
    return job


def enqueue_access_expiration_scan_job(
    db: Session,
    *,
    actor_user_id: str,
    correlation_id: str,
    warning_days: int,
) -> LifecycleJob:
    idempotency_key = _expiration_warning_key(correlation_id)
    existing_job = db.scalar(
        select(LifecycleJob).where(LifecycleJob.idempotency_key == idempotency_key)
    )
    if existing_job:
        return existing_job

    job = LifecycleJob(
        job_type="access_expiration_scan",
        status="queued",
        attempt_count=0,
        idempotency_key=idempotency_key,
        payload={
            "actor_user_id": actor_user_id,
            "correlation_id": correlation_id,
            "warning_days": warning_days,
        },
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        event_type="lifecycle_job.queued",
        actor_user_id=actor_user_id,
        target_type="lifecycle_job",
        target_id=job.id,
        action="enqueue_access_expiration_scan",
        result="queued",
        correlation_id=correlation_id,
        metadata_json={"warning_days": warning_days},
    )
    db.flush()
    return job


def _provision_jobs_for_request(db: Session, request: AccessRequest) -> list[LifecycleJob]:
    keys = [_provision_key(request.id, provider) for provider in request.provider_names]
    statement = select(LifecycleJob).where(LifecycleJob.idempotency_key.in_(keys))
    return list(db.scalars(statement).all())


def _complete_request_if_ready(db: Session, request: AccessRequest) -> None:
    jobs = _provision_jobs_for_request(db, request)
    if len(jobs) != len(request.provider_names):
        return
    if any(job.status == "failed" for job in jobs):
        if request.status == RequestStatus.PROVISIONING:
            request.status = transition(request.status, RequestStatus.PROVISIONING_FAILED)
        return
    if not all(job.status == "completed" for job in jobs):
        return

    request.status = transition(request.status, RequestStatus.ACTIVE)
    request.provisioned_at = datetime.now(UTC)
    request.expires_at = request.requested_end_at


async def run_provisioning_job(db: Session, job: LifecycleJob) -> ProviderAssignment | None:
    _start_job(job)
    payload = job.payload or {}
    request_id = str(payload.get("request_id", ""))
    provider = str(payload.get("provider", ""))
    correlation_id = str(payload.get("correlation_id", "worker"))
    request = db.get(AccessRequest, request_id)
    if not request or not provider:
        _fail_job(
            db,
            job=job,
            message="Provisioning job is missing request or provider context.",
            operation="provision_access",
            retryable=False,
            details={"code": "invalid_job_payload", "operation": "provision_access"},
        )
        return None

    existing_assignment = db.scalar(
        select(ProviderAssignment).where(
            ProviderAssignment.request_id == request.id,
            ProviderAssignment.provider == provider,
        )
    )
    if existing_assignment:
        job.status = "completed"
        _complete_request_if_ready(db, request)
        db.flush()
        return existing_assignment

    adapter = get_provider_adapter(provider)
    try:
        result = await adapter.provision_access(request.id, job.idempotency_key)
    except ProviderOperationError as exc:
        job.status = "failed"
        job.failure_information = {
            "retryable": exc.retryable,
            "message": str(exc),
            "details": safe_provider_error_details(exc.details),
        }
        if request.status == RequestStatus.PROVISIONING:
            request.status = transition(request.status, RequestStatus.PROVISIONING_FAILED)
        record_audit_event(
            db,
            event_type="provider.provision_failed",
            actor_user_id=None,
            target_type="lifecycle_job",
            target_id=job.id,
            request_id=request.id,
            project_id=request.project_id,
            provider=provider,
            action="provision_access",
            result="retryable_failure" if exc.retryable else "permanent_failure",
            correlation_id=correlation_id,
            reason=str(exc),
            metadata_json=job.failure_information,
        )
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="provisioning_failed",
            message=f"{request.project_name} was approved, but provisioning failed.",
        )
        db.flush()
        return None

    assignment = ProviderAssignment(
        request_id=request.id,
        project_id=request.project_id,
        provider=provider,
        status="active",
        external_resource_id=result["resource_id"],
        expires_at=request.requested_end_at,
    )
    db.add(assignment)
    job.status = "completed"
    record_audit_event(
        db,
        event_type="provider.provisioned",
        actor_user_id=None,
        target_type="provider_assignment",
        target_id=assignment.id,
        request_id=request.id,
        project_id=request.project_id,
        provider=provider,
        action="provision_access",
        result="success",
        correlation_id=correlation_id,
        metadata_json={
            "resource_id": result["resource_id"],
            "resource_type": result.get("resource_type", ""),
            "least_privilege_scope": result.get("least_privilege_scope", ""),
            "subject_type": result.get("subject_type", ""),
            "execution_mode": result.get("execution_mode", ""),
        },
    )
    _complete_request_if_ready(db, request)
    db.flush()
    return assignment


async def run_queued_lifecycle_jobs(db: Session, limit: int = 10) -> int:
    jobs = db.scalars(
        select(LifecycleJob)
        .where(
            LifecycleJob.status == "queued",
            LifecycleJob.job_type.in_(
                {
                    "provision_access",
                    "restore_access",
                    "archive_and_deprovision",
                    "cost_allocation_delivery",
                    "enforce_archive_retention",
                    "record_usage_and_cost",
                    "access_expiration_scan",
                }
            ),
        )
        .order_by(LifecycleJob.created_at.asc())
        .limit(limit)
    ).all()
    for job in jobs:
        if job.job_type == "provision_access":
            await run_provisioning_job(db, job)
        elif job.job_type == "restore_access":
            await run_restore_job(db, job)
        elif job.job_type == "archive_and_deprovision":
            await run_archive_and_deprovision_job(db, job)
        elif job.job_type == "cost_allocation_delivery":
            run_cost_allocation_delivery_job(db, job)
        elif job.job_type == "enforce_archive_retention":
            run_archive_retention_job(db, job)
        elif job.job_type == "record_usage_and_cost":
            run_usage_processing_job(db, job)
        elif job.job_type == "access_expiration_scan":
            run_access_expiration_scan_job(db, job)
    return len(jobs)


async def enqueue_and_maybe_run_provisioning(
    db: Session, request: AccessRequest, correlation_id: str
) -> list[LifecycleJob]:
    jobs = enqueue_provisioning_jobs(db, request, correlation_id)
    if get_settings().lifecycle_inline_execution:
        await run_queued_lifecycle_jobs(db, limit=max(len(jobs), 1))
    return jobs


async def enqueue_and_maybe_run_archive_retention(
    db: Session,
    *,
    actor_user_id: str,
    correlation_id: str,
) -> LifecycleJob:
    job = enqueue_archive_retention_job(
        db,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    if get_settings().lifecycle_inline_execution and job.status == "queued":
        await run_queued_lifecycle_jobs(db, limit=1)
    return job


async def enqueue_and_maybe_run_access_expiration_scan(
    db: Session,
    *,
    actor_user_id: str,
    correlation_id: str,
    warning_days: int | None = None,
) -> LifecycleJob:
    effective_warning_days = warning_days or get_settings().access_expiration_warning_days
    job = enqueue_access_expiration_scan_job(
        db,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        warning_days=effective_warning_days,
    )
    if get_settings().lifecycle_inline_execution and job.status == "queued":
        await run_queued_lifecycle_jobs(db, limit=1)
    return job


async def run_restore_job(db: Session, job: LifecycleJob) -> str | None:
    _start_job(job)
    payload = job.payload or {}
    assignment_id = str(payload.get("assignment_id", ""))
    actor_user_id = str(payload.get("actor_user_id", ""))
    reason = str(payload.get("reason", "Worker restore action."))
    correlation_id = str(payload.get("correlation_id", "worker"))
    assignment = db.get(ProviderAssignment, assignment_id)
    if not assignment or not actor_user_id:
        _fail_job(
            db,
            job=job,
            message="Restore job is missing assignment or actor context.",
            operation="restore_access",
            retryable=False,
            details={"code": "invalid_job_payload", "operation": "restore_access"},
        )
        return None
    try:
        return await restore_assignment(
            db,
            assignment=assignment,
            actor_user_id=actor_user_id,
            reason=reason,
            correlation_id=correlation_id,
            job=job,
        )
    except ProviderOperationError as exc:
        _fail_job(
            db,
            job=job,
            message=str(exc),
            operation="restore_access",
            retryable=exc.retryable,
            details=exc.details,
        )
        notify_roles(
            db,
            role_names={"platform_admin"},
            event_type="lifecycle_job_failed",
            message=f"Restore failed for {assignment.provider} assignment.",
        )
        return None


def run_archive_retention_job(db: Session, job: LifecycleJob) -> str:
    _start_job(job)
    payload = job.payload or {}
    actor_user_id = str(payload.get("actor_user_id", ""))
    correlation_id = str(payload.get("correlation_id", "worker"))
    if not actor_user_id:
        _fail_job(
            db,
            job=job,
            message="Archive retention job is missing actor context.",
            operation="enforce_archive_retention",
            retryable=False,
            details={"code": "invalid_job_payload", "operation": "enforce_archive_retention"},
        )
        return "lifecycle_job.failed"
    purged_count = enforce_archive_retention(
        db,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        job=job,
    )
    return f"artifact.retention_purged:{purged_count}"


async def run_archive_and_deprovision_job(db: Session, job: LifecycleJob) -> str | None:
    _start_job(job)
    payload = job.payload or {}
    assignment_id = str(payload.get("assignment_id", ""))
    actor_user_id = str(payload.get("actor_user_id", ""))
    reason = str(payload.get("reason", "Worker archive action."))
    correlation_id = str(payload.get("correlation_id", "worker"))
    assignment = db.get(ProviderAssignment, assignment_id)
    if not assignment or not actor_user_id:
        _fail_job(
            db,
            job=job,
            message="Archive job is missing assignment or actor context.",
            operation="archive_and_deprovision",
            retryable=False,
            details={"code": "invalid_job_payload", "operation": "archive_and_deprovision"},
        )
        return None
    try:
        event_type, _ = await expire_and_archive_assignment(
            db,
            assignment=assignment,
            actor_user_id=actor_user_id,
            reason=reason,
            correlation_id=correlation_id,
            job=job,
        )
        return event_type
    except ProviderOperationError as exc:
        _fail_job(
            db,
            job=job,
            message=str(exc),
            operation="archive_and_deprovision",
            retryable=exc.retryable,
            details=exc.details,
        )
        notify_roles(
            db,
            role_names={"platform_admin"},
            event_type="lifecycle_job_failed",
            message=f"Archive and deprovision failed for {assignment.provider} assignment.",
        )
        return None


async def enqueue_and_maybe_run_lifecycle_action(
    db: Session,
    *,
    assignment: ProviderAssignment,
    job_type: str,
    actor_user_id: str,
    reason: str,
    correlation_id: str,
) -> LifecycleJob:
    job = enqueue_lifecycle_action_job(
        db,
        assignment=assignment,
        job_type=job_type,
        actor_user_id=actor_user_id,
        reason=reason,
        correlation_id=correlation_id,
    )
    if get_settings().lifecycle_inline_execution and job.status == "queued":
        await run_queued_lifecycle_jobs(db, limit=1)
    return job


def run_usage_processing_job(db: Session, job: LifecycleJob) -> str | None:
    _start_job(job)
    payload = job.payload or {}
    assignment_id = str(payload.get("assignment_id", ""))
    actor_user_id = str(payload.get("actor_user_id", ""))
    correlation_id = str(payload.get("correlation_id", "worker"))
    assignment = db.get(ProviderAssignment, assignment_id)
    if not assignment or not actor_user_id:
        _fail_job(
            db,
            job=job,
            message="Usage processing job is missing assignment or actor context.",
            operation="record_usage_and_cost",
            retryable=False,
            details={"code": "invalid_job_payload", "operation": "record_usage_and_cost"},
        )
        return None
    try:
        event_type = record_usage_and_cost(
            db,
            assignment=assignment,
            actor_user_id=actor_user_id,
            tokens=int(payload.get("tokens", 0)),
            request_count=int(payload.get("request_count", 0)),
            cost_amount=Decimal(str(payload.get("cost_amount", "0"))),
            correlation_id=correlation_id,
        )
    except (ValueError, ArithmeticError) as exc:
        _fail_job(
            db,
            job=job,
            message=str(exc),
            operation="record_usage_and_cost",
            retryable=False,
            details={"code": "usage_processing_failed", "operation": "record_usage_and_cost"},
        )
        return None
    job.payload = {**payload, "audit_event": event_type}
    job.status = "completed"
    db.flush()
    return event_type


def run_access_expiration_scan_job(db: Session, job: LifecycleJob) -> str:
    _start_job(job)
    payload = job.payload or {}
    actor_user_id = str(payload.get("actor_user_id", ""))
    correlation_id = str(payload.get("correlation_id", "worker"))
    warning_days = int(payload.get("warning_days", get_settings().access_expiration_warning_days))
    if not actor_user_id:
        _fail_job(
            db,
            job=job,
            message="Expiration scan job is missing actor context.",
            operation="warn_expiring_access",
            retryable=False,
            details={"code": "invalid_job_payload", "operation": "warn_expiring_access"},
        )
        return "lifecycle_job.failed"
    warned_count = warn_expiring_access(
        db,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        job=job,
        warning_days=warning_days,
    )
    return f"lifecycle.expiration_warning:{warned_count}"


async def enqueue_and_maybe_run_usage_processing(
    db: Session,
    *,
    assignment: ProviderAssignment,
    actor_user_id: str,
    tokens: int,
    request_count: int,
    cost_amount: Decimal,
    correlation_id: str,
) -> LifecycleJob:
    job = enqueue_usage_processing_job(
        db,
        assignment=assignment,
        actor_user_id=actor_user_id,
        tokens=tokens,
        request_count=request_count,
        cost_amount=cost_amount,
        correlation_id=correlation_id,
    )
    if get_settings().lifecycle_inline_execution and job.status == "queued":
        await run_queued_lifecycle_jobs(db, limit=1)
    return job


def run_cost_allocation_delivery_job(db: Session, job: LifecycleJob) -> None:
    _start_job(job)
    payload = job.payload or {}
    correlation_id = str(payload.get("correlation_id", "worker"))
    _, row_count = cost_allocation_csv(db)
    job.payload = {
        **payload,
        "row_count": row_count,
        "format": str(payload.get("format", "csv")),
    }
    job.status = "completed"
    record_audit_event(
        db,
        event_type="report.cost_allocation_delivery_completed",
        actor_user_id=None,
        target_type="lifecycle_job",
        target_id=job.id,
        action="deliver_report",
        result="success",
        correlation_id=correlation_id,
        metadata_json={
            "frequency": payload.get("frequency", "weekly"),
            "recipients": payload.get("recipients", []),
            "row_count": row_count,
        },
    )
    db.flush()

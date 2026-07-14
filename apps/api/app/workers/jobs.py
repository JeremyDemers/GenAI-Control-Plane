from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AccessRequest, LifecycleJob, ProviderAssignment
from app.models.enums import RequestStatus
from app.providers.base import ProviderOperationError
from app.providers.registry import get_provider_adapter
from app.services.audit import record_audit_event
from app.services.notifications import notify_user
from app.services.state_machine import transition

SAFE_PROVIDER_ERROR_KEYS = {"code", "message", "operation", "provider_status", "retry_after"}


def safe_provider_error_details(details: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in details.items() if key in SAFE_PROVIDER_ERROR_KEYS}


def _provision_key(request_id: str, provider: str) -> str:
    return f"provision:{request_id}:{provider}"


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
    job.status = "running"
    if job.attempt_count == 0:
        job.attempt_count = 1
    job.failure_information = {}
    payload = job.payload or {}
    request_id = str(payload.get("request_id", ""))
    provider = str(payload.get("provider", ""))
    correlation_id = str(payload.get("correlation_id", "worker"))
    request = db.get(AccessRequest, request_id)
    if not request or not provider:
        job.status = "failed"
        job.failure_information = {
            "retryable": False,
            "message": "Provisioning job is missing request or provider context.",
            "details": {"code": "invalid_job_payload", "operation": "provision_access"},
        }
        db.flush()
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
        metadata_json={"resource_id": result["resource_id"]},
    )
    _complete_request_if_ready(db, request)
    db.flush()
    return assignment


async def run_queued_lifecycle_jobs(db: Session, limit: int = 10) -> int:
    jobs = db.scalars(
        select(LifecycleJob)
        .where(LifecycleJob.status == "queued", LifecycleJob.job_type == "provision_access")
        .order_by(LifecycleJob.created_at.asc())
        .limit(limit)
    ).all()
    for job in jobs:
        await run_provisioning_job(db, job)
    return len(jobs)


async def enqueue_and_maybe_run_provisioning(
    db: Session, request: AccessRequest, correlation_id: str
) -> list[LifecycleJob]:
    jobs = enqueue_provisioning_jobs(db, request, correlation_id)
    if get_settings().lifecycle_inline_execution:
        await run_queued_lifecycle_jobs(db, limit=max(len(jobs), 1))
    return jobs

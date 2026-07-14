from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import AccessRequest, LifecycleJob, ProviderAssignment
from app.models.enums import RequestStatus
from app.providers.base import ProviderOperationError
from app.providers.registry import get_provider_adapter
from app.services.audit import record_audit_event
from app.services.state_machine import transition

SAFE_PROVIDER_ERROR_KEYS = {"code", "message", "operation", "provider_status", "retry_after"}


def safe_provider_error_details(details: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in details.items() if key in SAFE_PROVIDER_ERROR_KEYS}


async def provision_request(
    db: Session, request: AccessRequest, correlation_id: str
) -> list[ProviderAssignment]:
    request.status = transition(request.status, RequestStatus.PROVISIONING)
    assignments: list[ProviderAssignment] = []
    for provider in request.provider_names:
        job = LifecycleJob(
            job_type="provision_access",
            status="running",
            attempt_count=1,
            idempotency_key=f"provision:{request.id}:{provider}",
        )
        db.add(job)
        db.flush()
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
            db.flush()
            return assignments
        assignment = ProviderAssignment(
            request_id=request.id,
            project_id=request.project_id,
            provider=provider,
            status="active",
            external_resource_id=result["resource_id"],
            expires_at=request.requested_end_at,
        )
        db.add(assignment)
        assignments.append(assignment)
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

    request.status = transition(request.status, RequestStatus.ACTIVE)
    request.provisioned_at = datetime.now(UTC)
    request.expires_at = request.requested_end_at
    db.flush()
    return assignments

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.database import get_db
from app.models.entities import (
    AccessRequest,
    ArtifactArchive,
    AuditEvent,
    LifecycleJob,
    ProviderAssignment,
    User,
)
from app.schemas import ProvisioningEvidenceOut

router = APIRouter(prefix="/evidence", tags=["evidence"])


def provision_key(request_id: str, provider: str) -> str:
    return f"provision:{request_id}:{provider}"


def archive_key(assignment_id: str) -> str:
    return f"archive:{assignment_id}"


@router.get("/provisioning", response_model=list[ProvisioningEvidenceOut])
def list_provisioning_evidence(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("evidence:read")),
) -> list[ProvisioningEvidenceOut]:
    assignments = db.scalars(
        select(ProviderAssignment).order_by(ProviderAssignment.created_at.desc()).limit(200)
    ).all()
    jobs = db.scalars(select(LifecycleJob)).all()
    jobs_by_key = {job.idempotency_key: job for job in jobs}
    archives_by_assignment = {
        archive.assignment_id: archive
        for archive in db.scalars(select(ArtifactArchive)).all()
        if archive.assignment_id is not None
    }
    closed_events_by_assignment = {
        event.target_id: event
        for event in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.event_type == "lifecycle.closed")
            .order_by(AuditEvent.created_at.desc())
        ).all()
        if event.target_id is not None
    }

    evidence: list[ProvisioningEvidenceOut] = []
    for assignment in assignments:
        request = db.get(AccessRequest, assignment.request_id)
        if request is None:
            continue
        provision_job = jobs_by_key.get(provision_key(request.id, assignment.provider))
        archive_job = jobs_by_key.get(archive_key(assignment.id))
        archive = archives_by_assignment.get(assignment.id)
        closed_event = closed_events_by_assignment.get(assignment.id)
        evidence_result = "closed" if closed_event else assignment.status
        evidence.append(
            ProvisioningEvidenceOut(
                assignment_id=assignment.id,
                request_id=request.id,
                project_id=assignment.project_id,
                project_name=request.project_name,
                provider=assignment.provider,
                assignment_status=assignment.status,
                external_resource_id=assignment.external_resource_id,
                provision_job_status=provision_job.status if provision_job else None,
                archive_job_status=archive_job.status if archive_job else None,
                archive_location=archive.storage_location if archive else None,
                archive_checksum=archive.checksum if archive else None,
                deprovisioned_at=closed_event.created_at if closed_event else None,
                evidence_result=evidence_result,
                updated_at=assignment.updated_at,
            )
        )
    return evidence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.lifecycle_jobs import job_out
from app.auth.dependencies import get_correlation_id, require_permission
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import AccessRequest, ArtifactArchive, ProviderAssignment, User
from app.schemas import (
    ArtifactArchiveOut,
    LifecycleActionIn,
    LifecycleActionOut,
    LifecycleJobOut,
    ProviderAssignmentOut,
    SimulatedUsageIn,
)
from app.services.lifecycle import assignment_totals
from app.workers.jobs import (
    enqueue_and_maybe_run_archive_retention,
    enqueue_and_maybe_run_lifecycle_action,
    enqueue_and_maybe_run_usage_processing,
)

router = APIRouter(prefix="/developer", tags=["developer controls"])


def ensure_local_development() -> None:
    if get_settings().environment != "local":
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Not available"}
        )


def assignment_out(db: Session, assignment: ProviderAssignment) -> ProviderAssignmentOut:
    total_cost, total_tokens, freshness_at = assignment_totals(db, assignment.id)
    return ProviderAssignmentOut(
        id=assignment.id,
        request_id=assignment.request_id,
        provider=assignment.provider,
        status=assignment.status,
        external_resource_id=assignment.external_resource_id,
        expires_at=assignment.expires_at,
        total_cost=total_cost,
        total_tokens=total_tokens,
        freshness_at=freshness_at,
    )


@router.get("/assignments", response_model=list[ProviderAssignmentOut])
def list_assignments(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin:*")),
) -> list[ProviderAssignmentOut]:
    ensure_local_development()
    assignments = db.scalars(
        select(ProviderAssignment).order_by(ProviderAssignment.created_at.desc())
    ).all()
    return [assignment_out(db, assignment) for assignment in assignments]


@router.post("/simulate-usage", response_model=LifecycleActionOut)
async def simulate_usage(
    payload: SimulatedUsageIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin:*")),
    correlation_id: str = Depends(get_correlation_id),
) -> LifecycleActionOut:
    ensure_local_development()
    assignment = db.get(ProviderAssignment, payload.assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Provider assignment not found."},
        )
    job = await enqueue_and_maybe_run_usage_processing(
        db,
        assignment=assignment,
        actor_user_id=user.id,
        tokens=payload.tokens,
        request_count=payload.request_count,
        cost_amount=payload.cost_amount,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(assignment)
    access_request = db.get(AccessRequest, assignment.request_id)
    if not access_request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request missing"}
        )
    return LifecycleActionOut(
        assignment_id=assignment.id,
        request_id=assignment.request_id,
        status=assignment.status,
        request_status=access_request.status,
        audit_event="lifecycle_job.queued"
        if job.status == "queued"
        else str(job.payload.get("audit_event", "budget.normal")),
    )


@router.post("/restore", response_model=LifecycleActionOut)
async def restore(
    payload: LifecycleActionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin:*")),
    correlation_id: str = Depends(get_correlation_id),
) -> LifecycleActionOut:
    ensure_local_development()
    assignment = db.get(ProviderAssignment, payload.assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Provider assignment not found."},
        )
    job = await enqueue_and_maybe_run_lifecycle_action(
        db,
        assignment=assignment,
        actor_user_id=user.id,
        job_type="restore_access",
        reason=payload.reason,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(assignment)
    access_request = db.get(AccessRequest, assignment.request_id)
    if not access_request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request missing"}
        )
    return LifecycleActionOut(
        assignment_id=assignment.id,
        request_id=assignment.request_id,
        status=assignment.status,
        request_status=access_request.status,
        audit_event="provider.restored" if job.status == "completed" else "lifecycle_job.queued",
    )


@router.post("/expire", response_model=LifecycleActionOut)
async def expire(
    payload: LifecycleActionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin:*")),
    correlation_id: str = Depends(get_correlation_id),
) -> LifecycleActionOut:
    ensure_local_development()
    assignment = db.get(ProviderAssignment, payload.assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Provider assignment not found."},
        )
    job = await enqueue_and_maybe_run_lifecycle_action(
        db,
        assignment=assignment,
        actor_user_id=user.id,
        job_type="archive_and_deprovision",
        reason=payload.reason,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(assignment)
    access_request = db.get(AccessRequest, assignment.request_id)
    if not access_request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request missing"}
        )
    return LifecycleActionOut(
        assignment_id=assignment.id,
        request_id=assignment.request_id,
        status=assignment.status,
        request_status=access_request.status,
        audit_event="lifecycle.closed" if job.status == "completed" else "lifecycle_job.queued",
    )


@router.get("/archives", response_model=list[ArtifactArchiveOut])
def list_archives(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin:*")),
) -> list[ArtifactArchiveOut]:
    ensure_local_development()
    archives = db.scalars(select(ArtifactArchive).order_by(ArtifactArchive.created_at.desc())).all()
    return [
        ArtifactArchiveOut(
            id=archive.id,
            assignment_id=archive.assignment_id,
            storage_provider=archive.storage_provider,
            storage_location=archive.storage_location,
            checksum=archive.checksum,
            retention_expires_at=archive.retention_expires_at,
        )
        for archive in archives
    ]


@router.post("/archives/enforce-retention", response_model=LifecycleJobOut)
async def enforce_retention(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin:*")),
    correlation_id: str = Depends(get_correlation_id),
) -> LifecycleJobOut:
    ensure_local_development()
    job = await enqueue_and_maybe_run_archive_retention(
        db,
        actor_user_id=user.id,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(job)
    return job_out(job)

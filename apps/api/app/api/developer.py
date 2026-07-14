from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import AccessRequest, ArtifactArchive, ProviderAssignment, User
from app.schemas import (
    ArtifactArchiveOut,
    LifecycleActionIn,
    LifecycleActionOut,
    ProviderAssignmentOut,
    SimulatedUsageIn,
)
from app.services.lifecycle import (
    assignment_totals,
    expire_and_archive_assignment,
    record_usage_and_cost,
    restore_assignment,
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
def simulate_usage(
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
    event_type = record_usage_and_cost(
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
        audit_event=event_type,
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
    event_type = await restore_assignment(
        db,
        assignment=assignment,
        actor_user_id=user.id,
        reason=payload.reason,
        correlation_id=correlation_id,
    )
    db.commit()
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
        audit_event=event_type,
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
    event_type, _ = await expire_and_archive_assignment(
        db,
        assignment=assignment,
        actor_user_id=user.id,
        reason=payload.reason,
        correlation_id=correlation_id,
    )
    db.commit()
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
        audit_event=event_type,
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

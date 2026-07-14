from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import AccessRequest, ExtensionRequest, ProviderAssignment, User
from app.models.enums import RequestStatus
from app.schemas import ExtensionDecisionIn, ExtensionRequestCreate, ExtensionRequestOut
from app.services.audit import record_audit_event
from app.services.notifications import notify_roles, notify_user

router = APIRouter(prefix="/extensions", tags=["extensions"])


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def extension_out(extension: ExtensionRequest) -> ExtensionRequestOut:
    return ExtensionRequestOut(
        id=extension.id,
        request_id=extension.request_id,
        requester_id=extension.requester_id,
        requested_end_at=extension.requested_end_at,
        status=extension.status,
        justification=extension.justification,
        created_at=extension.created_at,
        updated_at=extension.updated_at,
    )


@router.get("", response_model=list[ExtensionRequestOut])
def list_extensions(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ExtensionRequestOut]:
    role_names = {role.name for role in user.roles}
    statement = select(ExtensionRequest).order_by(ExtensionRequest.created_at.desc())
    if not ({"platform_admin", "cto", "security_auditor"} & role_names):
        statement = statement.where(ExtensionRequest.requester_id == user.id)
    return [extension_out(extension) for extension in db.scalars(statement).all()]


@router.post("", response_model=ExtensionRequestOut, status_code=201)
def create_extension_request(
    payload: ExtensionRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> ExtensionRequestOut:
    request = db.get(AccessRequest, payload.request_id)
    if not request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request not found."}
        )
    if request.requester_id != user.id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Only the requester can extend this request."},
        )
    if request.status not in {RequestStatus.ACTIVE, RequestStatus.EXPIRING_SOON}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REQUEST_NOT_EXTENDABLE",
                "message": "Only active or expiring access can be extended.",
            },
        )
    requested_end_at = aware_utc(payload.requested_end_at)
    current_end_at = aware_utc(request.requested_end_at)
    if requested_end_at <= current_end_at:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_EXTENSION_DATE",
                "message": "Extension end date must be after the current end date.",
            },
        )
    existing = db.scalar(
        select(ExtensionRequest).where(
            ExtensionRequest.request_id == request.id,
            ExtensionRequest.status == "pending",
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "EXTENSION_ALREADY_PENDING",
                "message": "An extension request is already pending.",
            },
        )
    extension = ExtensionRequest(
        request_id=request.id,
        requester_id=user.id,
        requested_end_at=requested_end_at,
        justification=payload.justification,
    )
    db.add(extension)
    db.flush()
    notify_roles(
        db,
        role_names={"platform_admin", "cto"},
        event_type="extension_requested",
        message=f"{request.project_name} needs an access extension decision.",
    )
    record_audit_event(
        db,
        event_type="extension.requested",
        actor_user_id=user.id,
        target_type="extension_request",
        target_id=extension.id,
        request_id=request.id,
        action="request_extension",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"requested_end_at": requested_end_at.isoformat()},
    )
    db.commit()
    db.refresh(extension)
    return extension_out(extension)


@router.post("/{extension_id}/decision", response_model=ExtensionRequestOut)
def decide_extension_request(
    extension_id: str,
    payload: ExtensionDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("extensions:approve")),
    correlation_id: str = Depends(get_correlation_id),
) -> ExtensionRequestOut:
    extension = db.get(ExtensionRequest, extension_id)
    if not extension:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Extension not found."}
        )
    if extension.status != "pending":
        raise HTTPException(
            status_code=400,
            detail={"code": "EXTENSION_NOT_PENDING", "message": "Extension is not pending."},
        )
    request = db.get(AccessRequest, extension.request_id)
    if not request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request not found."}
        )
    extension.status = "approved" if payload.decision == "approve" else "rejected"
    if payload.decision == "approve":
        request.requested_end_at = extension.requested_end_at
        request.expires_at = extension.requested_end_at
        assignments = db.scalars(
            select(ProviderAssignment).where(ProviderAssignment.request_id == request.id)
        ).all()
        for assignment in assignments:
            assignment.expires_at = extension.requested_end_at
    notify_user(
        db,
        user_id=extension.requester_id,
        event_type=f"extension_{extension.status}",
        message=f"{request.project_name} extension was {extension.status}.",
    )
    record_audit_event(
        db,
        event_type=f"extension.{extension.status}",
        actor_user_id=user.id,
        target_type="extension_request",
        target_id=extension.id,
        request_id=request.id,
        action=payload.decision,
        result="success",
        reason=payload.comments,
        correlation_id=correlation_id,
        metadata_json={"requested_end_at": extension.requested_end_at.isoformat()},
    )
    db.commit()
    db.refresh(extension)
    return extension_out(extension)

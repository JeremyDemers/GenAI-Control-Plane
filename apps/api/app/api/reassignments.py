from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_correlation_id
from app.core.database import get_db
from app.core.security import has_permission
from app.models.entities import Project, ProjectMember, ReassignmentRequest, User
from app.schemas import ReassignmentCreate, ReassignmentDecisionIn, ReassignmentOut
from app.services.audit import record_audit_event
from app.services.notifications import notify_roles, notify_user

router = APIRouter(prefix="/reassignments", tags=["reassignments"])


def is_project_owner(db: Session, project: Project, user: User) -> bool:
    if project.owner_user_id == user.id:
        return True
    return db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
            ProjectMember.member_role == "owner",
        )
    ) is not None


def user_by_id(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "User not found."}
        )
    return user


def to_reassignment_out(db: Session, reassignment: ReassignmentRequest) -> ReassignmentOut:
    project = db.get(Project, reassignment.project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Project not found."},
        )
    current_owner = user_by_id(db, reassignment.current_owner_id)
    proposed_owner = user_by_id(db, reassignment.proposed_owner_id)
    return ReassignmentOut(
        id=reassignment.id,
        project_id=project.id,
        project_name=project.name,
        current_owner_id=current_owner.id,
        current_owner_email=current_owner.email,
        proposed_owner_id=proposed_owner.id,
        proposed_owner_email=proposed_owner.email,
        status=reassignment.status,
        justification=reassignment.justification,
        created_at=reassignment.created_at,
        updated_at=reassignment.updated_at,
    )


def ensure_project_member(
    db: Session, *, project_id: str, user_id: str, member_role: str
) -> ProjectMember:
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if member:
        member.member_role = member_role
        return member
    member = ProjectMember(project_id=project_id, user_id=user_id, member_role=member_role)
    db.add(member)
    db.flush()
    return member


@router.get("", response_model=list[ReassignmentOut])
def list_reassignments(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ReassignmentOut]:
    role_names = {role.name for role in user.roles}
    statement = select(ReassignmentRequest).order_by(ReassignmentRequest.created_at.desc())
    if not has_permission(role_names, "reassignments:read_all"):
        statement = statement.where(
            or_(
                ReassignmentRequest.current_owner_id == user.id,
                ReassignmentRequest.proposed_owner_id == user.id,
            )
        )
    return [to_reassignment_out(db, reassignment) for reassignment in db.scalars(statement).all()]


@router.post("", response_model=ReassignmentOut, status_code=status.HTTP_201_CREATED)
def create_reassignment(
    payload: ReassignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> ReassignmentOut:
    project = db.get(Project, payload.project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Project not found."},
        )
    if not is_project_owner(db, project, user):
        record_audit_event(
            db,
            event_type="authorization.failure",
            actor_user_id=user.id,
            target_type="project",
            target_id=project.id,
            action="request_reassignment",
            result="denied",
            reason="Only the current project owner can request reassignment.",
            correlation_id=correlation_id,
            project_id=project.id,
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Only the current project owner can request reassignment.",
            },
        )

    proposed_owner = db.scalar(select(User).where(User.email == payload.proposed_owner_email))
    if not proposed_owner or not proposed_owner.is_active:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Proposed owner not found."},
        )
    if proposed_owner.id == user.id:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": "Choose a different owner."},
        )
    pending = db.scalar(
        select(ReassignmentRequest).where(
            ReassignmentRequest.project_id == project.id,
            ReassignmentRequest.status.in_(["pending_acceptance", "pending_approval"]),
        )
    )
    if pending:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": "A reassignment is already pending."},
        )

    reassignment = ReassignmentRequest(
        project_id=project.id,
        current_owner_id=user.id,
        proposed_owner_id=proposed_owner.id,
        status="pending_acceptance",
        justification=payload.justification,
    )
    db.add(reassignment)
    db.flush()
    notify_user(
        db,
        user_id=proposed_owner.id,
        event_type="reassignment_requested",
        message=f"{project.name} ownership was proposed for reassignment to you.",
    )
    record_audit_event(
        db,
        event_type="project.reassignment_requested",
        actor_user_id=user.id,
        target_type="reassignment",
        target_id=reassignment.id,
        action="request_reassignment",
        result="success",
        reason=payload.justification,
        correlation_id=correlation_id,
        project_id=project.id,
        metadata_json={"proposed_owner_email": proposed_owner.email},
    )
    db.commit()
    db.refresh(reassignment)
    return to_reassignment_out(db, reassignment)


@router.post("/{reassignment_id}/accept", response_model=ReassignmentOut)
def accept_reassignment(
    reassignment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> ReassignmentOut:
    reassignment = db.get(ReassignmentRequest, reassignment_id)
    if not reassignment or reassignment.status != "pending_acceptance":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REQUEST_NOT_ACTIONABLE",
                "message": "Reassignment is not awaiting owner acceptance.",
            },
        )
    if reassignment.proposed_owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Only the proposed owner can accept."},
        )
    project = db.get(Project, reassignment.project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."}
        )

    reassignment.status = "pending_approval"
    notify_roles(
        db,
        role_names={"platform_admin", "cto"},
        event_type="reassignment_approval_required",
        message=f"{project.name} ownership reassignment needs approval.",
    )
    record_audit_event(
        db,
        event_type="project.reassignment_accepted",
        actor_user_id=user.id,
        target_type="reassignment",
        target_id=reassignment.id,
        action="accept_reassignment",
        result="success",
        correlation_id=correlation_id,
        project_id=project.id,
    )
    db.commit()
    db.refresh(reassignment)
    return to_reassignment_out(db, reassignment)


@router.post("/{reassignment_id}/decision", response_model=ReassignmentOut)
def decide_reassignment(
    reassignment_id: str,
    payload: ReassignmentDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> ReassignmentOut:
    role_names = {role.name for role in user.roles}
    if not has_permission(role_names, "reassignments:approve"):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Reassignment approval is privileged."},
        )
    reassignment = db.get(ReassignmentRequest, reassignment_id)
    if not reassignment or reassignment.status != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REQUEST_NOT_ACTIONABLE",
                "message": "Reassignment is not awaiting approval.",
            },
        )
    project = db.get(Project, reassignment.project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."}
        )
    current_owner = user_by_id(db, reassignment.current_owner_id)
    proposed_owner = user_by_id(db, reassignment.proposed_owner_id)

    if payload.decision == "reject":
        reassignment.status = "rejected"
        event_type = "project.reassignment_rejected"
        action = "reject_reassignment"
    else:
        reassignment.status = "approved"
        project.owner_user_id = proposed_owner.id
        proposed_owner_member = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == proposed_owner.id,
            )
        )
        proposed_owner_old_role = (
            proposed_owner_member.member_role if proposed_owner_member else "none"
        )
        ensure_project_member(
            db, project_id=project.id, user_id=proposed_owner.id, member_role="owner"
        )
        old_owner_member = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == current_owner.id,
            )
        )
        current_owner_old_role = old_owner_member.member_role if old_owner_member else "owner"
        if old_owner_member:
            old_owner_member.member_role = "collaborator"
        event_type = "project.reassigned"
        action = "approve_reassignment"

    notification_type = (
        "project_reassigned" if payload.decision == "approve" else "reassignment_rejected"
    )
    notify_user(
        db,
        user_id=current_owner.id,
        event_type=notification_type,
        message=f"{project.name} reassignment was {reassignment.status}.",
    )
    notify_user(
        db,
        user_id=proposed_owner.id,
        event_type=notification_type,
        message=f"{project.name} reassignment was {reassignment.status}.",
    )
    record_audit_event(
        db,
        event_type=event_type,
        actor_user_id=user.id,
        target_type="reassignment",
        target_id=reassignment.id,
        action=action,
        result="success",
        reason=payload.comments,
        correlation_id=correlation_id,
        project_id=project.id,
        metadata_json={
            "current_owner_email": current_owner.email,
            "current_owner_old_role": current_owner_old_role,
            "current_owner_new_role": "collaborator",
            "proposed_owner_email": proposed_owner.email,
            "proposed_owner_old_role": proposed_owner_old_role,
            "proposed_owner_new_role": "owner",
        },
    )
    db.commit()
    db.refresh(reassignment)
    return to_reassignment_out(db, reassignment)

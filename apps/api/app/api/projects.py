from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_correlation_id
from app.core.database import get_db
from app.core.security import has_permission
from app.models.entities import AccessRequest, Project, ProjectMember, ProviderAssignment, User
from app.models.enums import RequestStatus
from app.schemas import ProjectMemberCreate, ProjectMemberOut, ProjectOut, ProjectSuspendIn
from app.services.audit import record_audit_event
from app.services.notifications import notify_user
from app.services.visibility import can_read_all

router = APIRouter(prefix="/projects", tags=["projects"])


def can_view_project(db: Session, project_id: str, user: User) -> bool:
    role_names = {role.name for role in user.roles}
    if can_read_all(role_names):
        return True
    return db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    ) is not None


def can_manage_project(db: Session, project: Project, user: User) -> bool:
    role_names = {role.name for role in user.roles}
    if not has_permission(role_names, "projects:members"):
        return False
    if has_permission(role_names, "admin:*"):
        return True
    if project.owner_user_id == user.id:
        return True
    return db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
            ProjectMember.member_role == "owner",
        )
    ) is not None


def project_out(db: Session, project: Project) -> ProjectOut:
    member_count = db.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project.id)
    )
    return ProjectOut(
        id=project.id,
        name=project.name,
        cost_center=project.cost_center,
        owner_user_id=project.owner_user_id,
        status=project.status,
        member_count=int(member_count or 0),
        created_at=project.created_at,
    )


def project_member_out(member: ProjectMember, member_user: User) -> ProjectMemberOut:
    return ProjectMemberOut(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        email=member_user.email,
        display_name=member_user.display_name,
        member_role=member.member_role,
        created_at=member.created_at,
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ProjectOut]:
    role_names = {role.name for role in user.roles}
    statement = select(Project).order_by(Project.created_at.desc())
    if not can_read_all(role_names):
        project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        statement = statement.where(Project.id.in_(project_ids))
    return [project_out(db, project) for project in db.scalars(statement).all()]


@router.post("/{project_id}/suspend", response_model=ProjectOut)
def suspend_project(
    project_id: str,
    payload: ProjectSuspendIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> ProjectOut:
    role_names = {role.name for role in user.roles}
    if not has_permission(role_names, "projects:suspend"):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Project suspension is privileged."},
        )
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Project not found."},
        )
    if project.status == "suspended":
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": "Project is already suspended."},
        )

    project.status = "suspended"
    requests = db.scalars(
        select(AccessRequest).where(AccessRequest.project_id == project.id)
    ).all()
    for access_request in requests:
        if access_request.status == RequestStatus.ACTIVE:
            access_request.status = RequestStatus.SUSPENDED
        assignments = db.scalars(
            select(ProviderAssignment).where(
                ProviderAssignment.request_id == access_request.id,
                ProviderAssignment.status == "active",
            )
        ).all()
        for assignment in assignments:
            assignment.status = "suspended"

    member_user_ids = db.scalars(
        select(ProjectMember.user_id).where(ProjectMember.project_id == project.id)
    ).all()
    for member_user_id in set(member_user_ids):
        notify_user(
            db,
            user_id=member_user_id,
            event_type="project_suspended",
            message=f"{project.name} was suspended: {payload.reason}",
        )
    record_audit_event(
        db,
        event_type="project.suspended",
        actor_user_id=user.id,
        target_type="project",
        target_id=project.id,
        action="suspend_project",
        result="success",
        reason=payload.reason,
        correlation_id=correlation_id,
        project_id=project.id,
        metadata_json={"affected_requests": len(requests)},
    )
    db.commit()
    db.refresh(project)
    return project_out(db, project)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    project_id: str,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> ProjectMemberOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Project not found."},
        )
    if not can_manage_project(db, project, user):
        record_audit_event(
            db,
            event_type="authorization.failure",
            actor_user_id=user.id,
            target_type="project",
            target_id=project.id,
            action="add_project_member",
            result="denied",
            reason="Project membership management requires project ownership.",
            correlation_id=correlation_id,
            project_id=project.id,
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Only project owners and platform admins can manage members.",
            },
        )

    target_user = db.scalar(select(User).where(User.email == payload.email))
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "User not found."},
        )
    existing = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == target_user.id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": "User is already a project member."},
        )

    member = ProjectMember(
        project_id=project.id,
        user_id=target_user.id,
        member_role=payload.member_role,
    )
    db.add(member)
    if payload.member_role == "owner":
        project.owner_user_id = target_user.id
    db.flush()

    notify_user(
        db,
        user_id=target_user.id,
        event_type="project_member_added",
        message=f"You were added to {project.name} as {payload.member_role}.",
    )
    record_audit_event(
        db,
        event_type="project.member_added",
        actor_user_id=user.id,
        target_type="project_member",
        target_id=member.id,
        action="add_project_member",
        result="success",
        reason=f"Added {target_user.email} as {payload.member_role}.",
        correlation_id=correlation_id,
        project_id=project.id,
        metadata_json={"email": target_user.email, "member_role": payload.member_role},
    )
    db.commit()
    db.refresh(member)
    return project_member_out(member, target_user)


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ProjectMemberOut]:
    if not can_view_project(db, project_id, user):
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Project not found."},
        )
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc())
    ).all()
    return [project_member_out(member, member_user) for member, member_user in rows]

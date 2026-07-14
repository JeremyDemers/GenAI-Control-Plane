from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.core.database import get_db
from app.models.entities import Project, ProjectMember, User
from app.schemas import ProjectMemberOut, ProjectOut
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
    return [
        ProjectMemberOut(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            email=member_user.email,
            display_name=member_user.display_name,
            member_role=member.member_role,
            created_at=member.created_at,
        )
        for member, member_user in rows
    ]

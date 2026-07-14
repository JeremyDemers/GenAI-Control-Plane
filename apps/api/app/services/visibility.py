from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.entities import AccessRequest, ApprovalStep, ProjectMember, User


def can_read_all(role_names: set[str]) -> bool:
    return bool({"platform_admin", "security_auditor", "cto"} & role_names)


def visible_request_ids(db: Session, user: User) -> list[str] | None:
    role_names = {role.name for role in user.roles}
    if can_read_all(role_names):
        return None

    project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    clauses = [
        AccessRequest.requester_id == user.id,
        AccessRequest.project_id.in_(project_ids),
    ]
    if {"approver", "security_reviewer"} & role_names:
        assigned_request_ids = select(ApprovalStep.request_id).where(
            ApprovalStep.assigned_role.in_(role_names)
        )
        clauses.append(AccessRequest.id.in_(assigned_request_ids))

    rows = db.scalars(select(AccessRequest.id).where(or_(*clauses))).all()
    return list(rows)

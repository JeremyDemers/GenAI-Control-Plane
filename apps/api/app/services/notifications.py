from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Notification, Role, User


def notify_user(db: Session, *, user_id: str, event_type: str, message: str) -> Notification:
    notification = Notification(user_id=user_id, event_type=event_type, message=message)
    db.add(notification)
    db.flush()
    return notification


def notify_roles(
    db: Session, *, role_names: Iterable[str], event_type: str, message: str
) -> list[Notification]:
    role_set = set(role_names)
    if not role_set:
        return []
    users = (
        db.scalars(select(User).join(User.roles).where(Role.name.in_(role_set)))
        .unique()
        .all()
    )
    return [
        notify_user(db, user_id=user.id, event_type=event_type, message=message)
        for user in users
    ]


APPROVAL_ROLE_BY_STEP = {
    "manager": "approver",
    "security": "security_reviewer",
    "cto": "cto",
}


def notify_approval_step(
    db: Session, *, step_type: str, project_name: str, request_id: str
) -> list[Notification]:
    role = APPROVAL_ROLE_BY_STEP[step_type]
    return notify_roles(
        db,
        role_names={role},
        event_type="approval_required",
        message=f"{project_name} needs {step_type} approval ({request_id}).",
    )

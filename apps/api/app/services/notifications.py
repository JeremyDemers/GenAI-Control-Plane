from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Notification, Role, User
from app.services.audit import record_audit_event


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


def deliver_pending_notifications(db: Session, limit: int = 25) -> int:
    notifications = db.scalars(
        select(Notification)
        .where(Notification.delivery_status == "pending")
        .order_by(Notification.created_at.asc())
        .limit(limit)
    ).all()
    now = datetime.now(UTC)
    for notification in notifications:
        notification.delivery_status = "delivered"
        notification.delivery_attempts += 1
        notification.delivered_at = now
        record_audit_event(
            db,
            event_type="notification.delivered",
            actor_user_id=None,
            target_type="notification",
            target_id=notification.id,
            action="deliver_notification",
            result="success",
            correlation_id="notification-worker",
            metadata_json={
                "event_type": notification.event_type,
                "user_id": notification.user_id,
                "delivery_attempts": notification.delivery_attempts,
            },
        )
    db.flush()
    return len(notifications)

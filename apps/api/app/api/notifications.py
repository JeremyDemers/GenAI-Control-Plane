from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.core.database import get_db
from app.models.entities import Notification, User
from app.schemas import NotificationOut, NotificationReadAllOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def to_notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        user_id=notification.user_id,
        event_type=notification.event_type,
        message=notification.message,
        read_at=notification.read_at,
        delivery_status=notification.delivery_status,
        delivery_attempts=notification.delivery_attempts,
        delivered_at=notification.delivered_at,
        created_at=notification.created_at,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[NotificationOut]:
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [to_notification_out(notification) for notification in notifications]


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> NotificationOut:
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Notification not found."},
        )
    notification.read_at = notification.read_at or datetime.now(UTC)
    db.commit()
    db.refresh(notification)
    return to_notification_out(notification)


@router.post("/read-all", response_model=NotificationReadAllOut)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> NotificationReadAllOut:
    unread_notifications = db.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ).all()
    now = datetime.now(UTC)
    for notification in unread_notifications:
        notification.read_at = now
    db.commit()
    return NotificationReadAllOut(marked_read=len(unread_notifications))

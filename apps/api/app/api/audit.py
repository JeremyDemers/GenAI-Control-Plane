from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.database import get_db
from app.models.entities import AuditEvent, User
from app.schemas import AuditEventOut

router = APIRouter(prefix="/audit-events", tags=["audit events"])


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read_all")),
) -> list[AuditEventOut]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return [
        AuditEventOut(
            id=event.id,
            event_type=event.event_type,
            actor_user_id=event.actor_user_id,
            target_type=event.target_type,
            target_id=event.target_id,
            action=event.action,
            result=event.result,
            reason=event.reason,
            correlation_id=event.correlation_id,
            created_at=event.created_at,
        )
        for event in events
    ]

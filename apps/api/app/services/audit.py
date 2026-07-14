from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AuditEvent


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    actor_user_id: str | None,
    target_type: str,
    target_id: str | None,
    action: str,
    result: str,
    correlation_id: str,
    reason: str = "",
    request_id: str | None = None,
    project_id: str | None = None,
    provider: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        request_id=request_id,
        project_id=project_id,
        provider=provider,
        action=action,
        result=result,
        reason=reason,
        correlation_id=correlation_id,
        metadata_json=metadata_json or {},
    )
    db.add(event)
    db.flush()
    return event

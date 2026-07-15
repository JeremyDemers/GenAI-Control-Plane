import csv
import json
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import AuditEvent, User
from app.schemas import AuditEventOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/audit-events", tags=["audit events"])


AUDIT_EXPORT_FIELDS = [
    "id",
    "event_type",
    "actor_user_id",
    "target_type",
    "target_id",
    "request_id",
    "project_id",
    "provider",
    "action",
    "result",
    "reason",
    "correlation_id",
    "metadata_json",
    "created_at",
]


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
            request_id=event.request_id,
            project_id=event.project_id,
            provider=event.provider,
            action=event.action,
            result=event.result,
            reason=event.reason,
            correlation_id=event.correlation_id,
            metadata_json=event.metadata_json,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.get("/export")
def export_audit_events(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit:export")),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(1000)).all()
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=AUDIT_EXPORT_FIELDS)
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor_user_id": event.actor_user_id or "",
                "target_type": event.target_type,
                "target_id": event.target_id or "",
                "request_id": event.request_id or "",
                "project_id": event.project_id or "",
                "provider": event.provider or "",
                "action": event.action,
                "result": event.result,
                "reason": event.reason,
                "correlation_id": event.correlation_id,
                "metadata_json": json.dumps(event.metadata_json, sort_keys=True),
                "created_at": event.created_at.isoformat(),
            }
        )
    record_audit_event(
        db,
        event_type="audit.exported",
        actor_user_id=user.id,
        target_type="audit_event",
        target_id=None,
        action="export",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"format": "csv", "row_count": len(events)},
    )
    db.commit()
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-events.csv"'},
    )

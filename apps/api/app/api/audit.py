import csv
import json
from collections import Counter
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import AuditEvent, User
from app.schemas import AuditEventOut, AuditEventSummaryItem, AuditEventSummaryOut
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


def _audit_event_query(
    *,
    event_type: str | None,
    correlation_id: str | None,
    target_type: str | None,
    result: str | None,
) -> Select[tuple[AuditEvent]]:
    statement = select(AuditEvent)
    if event_type:
        statement = statement.where(AuditEvent.event_type == event_type)
    if correlation_id:
        statement = statement.where(AuditEvent.correlation_id == correlation_id)
    if target_type:
        statement = statement.where(AuditEvent.target_type == target_type)
    if result:
        statement = statement.where(AuditEvent.result == result)
    return statement.order_by(AuditEvent.created_at.desc())


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(
    event_type: str | None = None,
    correlation_id: str | None = None,
    target_type: str | None = None,
    result: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read_all")),
) -> list[AuditEventOut]:
    events = db.scalars(
        _audit_event_query(
            event_type=event_type,
            correlation_id=correlation_id,
            target_type=target_type,
            result=result,
        ).limit(limit)
    ).all()
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


@router.get("/summary", response_model=AuditEventSummaryOut)
def summarize_audit_events(
    event_type: str | None = None,
    correlation_id: str | None = None,
    target_type: str | None = None,
    result: str | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read_all")),
) -> AuditEventSummaryOut:
    events = db.scalars(
        _audit_event_query(
            event_type=event_type,
            correlation_id=correlation_id,
            target_type=target_type,
            result=result,
        ).limit(limit)
    ).all()
    event_type_counts = Counter(event.event_type for event in events)
    result_counts = Counter(event.result for event in events)

    return AuditEventSummaryOut(
        total_events=len(events),
        unique_correlations=len({event.correlation_id for event in events}),
        success_events=result_counts["success"],
        failure_events=sum(count for name, count in result_counts.items() if name != "success"),
        by_event_type=[
            AuditEventSummaryItem(name=name, count=count)
            for name, count in event_type_counts.most_common(8)
        ],
        by_result=[
            AuditEventSummaryItem(name=name, count=count)
            for name, count in result_counts.most_common()
        ],
    )


@router.get("/export")
def export_audit_events(
    event_type: str | None = None,
    correlation_id: str | None = None,
    target_type: str | None = None,
    result: str | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit:export")),
    request_correlation_id: str = Depends(get_correlation_id),
) -> Response:
    events = db.scalars(
        _audit_event_query(
            event_type=event_type,
            correlation_id=correlation_id,
            target_type=target_type,
            result=result,
        ).limit(limit)
    ).all()
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
        correlation_id=request_correlation_id,
        metadata_json={
            "format": "csv",
            "row_count": len(events),
            "filters": {
                "event_type": event_type,
                "correlation_id": correlation_id,
                "target_type": target_type,
                "result": result,
                "limit": limit,
            },
        },
    )
    db.commit()
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-events.csv"'},
    )

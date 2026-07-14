from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import Incident, User
from app.schemas import IncidentOut, IncidentResolveIn
from app.services.audit import record_audit_event

router = APIRouter(prefix="/incidents", tags=["incidents"])


def incident_out(incident: Incident) -> IncidentOut:
    return IncidentOut(
        id=incident.id,
        severity=incident.severity,
        status=incident.status,
        summary=incident.summary,
        metadata_json=incident.metadata_json,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("incidents:read")),
) -> list[IncidentOut]:
    incidents = db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(100)).all()
    return [incident_out(incident) for incident in incidents]


@router.post("/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(
    incident_id: str,
    payload: IncidentResolveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:manage")),
    correlation_id: str = Depends(get_correlation_id),
) -> IncidentOut:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Incident not found."}
        )
    if incident.status == "resolved":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INCIDENT_ALREADY_RESOLVED",
                "message": "Incident is already resolved.",
            },
        )
    incident.status = "resolved"
    incident.metadata_json = {**incident.metadata_json, "resolution_reason": payload.reason}
    record_audit_event(
        db,
        event_type="incident.resolved",
        actor_user_id=user.id,
        target_type="incident",
        target_id=incident.id,
        action="resolve",
        result="success",
        reason=payload.reason,
        correlation_id=correlation_id,
        metadata_json={"severity": incident.severity},
    )
    db.commit()
    db.refresh(incident)
    return incident_out(incident)

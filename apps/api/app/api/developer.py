from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import CostRecord, Incident, ProviderAssignment, User
from app.services.audit import record_audit_event

router = APIRouter(prefix="/developer", tags=["developer controls"])


class SimulatedCostIn(BaseModel):
    assignment_id: str
    amount: Decimal = Field(gt=0)


@router.post("/simulate-cost")
def simulate_cost(
    payload: SimulatedCostIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin:*")),
    correlation_id: str = Depends(get_correlation_id),
) -> dict[str, str]:
    if get_settings().environment != "local":
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Not available"}
        )
    assignment = db.get(ProviderAssignment, payload.assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Provider assignment not found."},
        )
    db.add(
        CostRecord(
            assignment_id=assignment.id,
            provider=assignment.provider,
            amount=payload.amount,
            currency="USD",
            cost_type="estimated",
        )
    )
    if payload.amount >= Decimal("100"):
        assignment.status = "suspended"
        db.add(
            Incident(
                severity="high",
                summary=f"Budget enforcement suspended {assignment.provider} assignment",
                metadata_json={"assignment_id": assignment.id, "amount": str(payload.amount)},
            )
        )
    record_audit_event(
        db,
        event_type="developer.simulated_cost",
        actor_user_id=user.id,
        target_type="provider_assignment",
        target_id=assignment.id,
        provider=assignment.provider,
        action="simulate_cost",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"amount": str(payload.amount)},
    )
    db.commit()
    return {"status": assignment.status}

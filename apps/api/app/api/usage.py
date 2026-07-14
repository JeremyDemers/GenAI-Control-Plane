from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.core.database import get_db
from app.models.entities import (
    AccessRequest,
    ApprovalStep,
    CostRecord,
    ProviderAssignment,
    UsageRecord,
    User,
)
from app.schemas import (
    BudgetSummaryOut,
    CostRecordOut,
    ProviderAssignmentOut,
    UsageRecordOut,
)
from app.services.lifecycle import assignment_totals


def can_read_all(role_names: set[str]) -> bool:
    return bool({"platform_admin", "security_auditor", "cto"} & role_names)


def visible_request_ids(db: Session, user: User) -> list[str] | None:
    role_names = {role.name for role in user.roles}
    if can_read_all(role_names):
        return None
    if {"approver", "security_reviewer"} & role_names:
        assigned = select(ApprovalStep.request_id).where(ApprovalStep.assigned_role.in_(role_names))
        rows = db.scalars(
            select(AccessRequest.id).where(
                or_(AccessRequest.requester_id == user.id, AccessRequest.id.in_(assigned))
            )
        ).all()
        return list(rows)
    rows = db.scalars(select(AccessRequest.id).where(AccessRequest.requester_id == user.id)).all()
    return list(rows)


def assignment_out(db: Session, assignment: ProviderAssignment) -> ProviderAssignmentOut:
    total_cost, total_tokens, freshness_at = assignment_totals(db, assignment.id)
    return ProviderAssignmentOut(
        id=assignment.id,
        request_id=assignment.request_id,
        provider=assignment.provider,
        status=assignment.status,
        external_resource_id=assignment.external_resource_id,
        expires_at=assignment.expires_at,
        total_cost=total_cost,
        total_tokens=total_tokens,
        freshness_at=freshness_at,
    )


def require_visible_assignment(db: Session, assignment_id: str, user: User) -> ProviderAssignment:
    assignment = db.get(ProviderAssignment, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Provider assignment not found."},
        )
    request_ids = visible_request_ids(db, user)
    if request_ids is not None and assignment.request_id not in request_ids:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Assignment is not visible."},
        )
    return assignment


assignments_router = APIRouter(prefix="/provider-assignments", tags=["provider assignments"])
usage_router = APIRouter(prefix="/usage", tags=["usage"])
costs_router = APIRouter(prefix="/costs", tags=["costs"])
budgets_router = APIRouter(prefix="/budgets", tags=["budgets"])


@assignments_router.get("", response_model=list[ProviderAssignmentOut])
def list_provider_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ProviderAssignmentOut]:
    request_ids = visible_request_ids(db, user)
    statement = select(ProviderAssignment).order_by(ProviderAssignment.created_at.desc())
    if request_ids is not None:
        statement = statement.where(ProviderAssignment.request_id.in_(request_ids))
    return [assignment_out(db, assignment) for assignment in db.scalars(statement).all()]


@usage_router.get("", response_model=list[UsageRecordOut])
def list_usage_records(
    assignment_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[UsageRecordOut]:
    if assignment_id:
        require_visible_assignment(db, assignment_id, user)
    visible_ids = visible_request_ids(db, user)
    statement = select(UsageRecord).order_by(UsageRecord.measured_at.desc())
    if assignment_id:
        statement = statement.where(UsageRecord.assignment_id == assignment_id)
    elif visible_ids is not None:
        assignment_ids = select(ProviderAssignment.id).where(
            ProviderAssignment.request_id.in_(visible_ids)
        )
        statement = statement.where(UsageRecord.assignment_id.in_(assignment_ids))
    records = db.scalars(statement.limit(200)).all()
    return [
        UsageRecordOut(
            id=record.id,
            assignment_id=record.assignment_id,
            provider=record.provider,
            tokens=record.tokens,
            request_count=record.request_count,
            measured_at=record.measured_at,
            freshness_at=record.freshness_at,
        )
        for record in records
    ]


@costs_router.get("", response_model=list[CostRecordOut])
def list_cost_records(
    assignment_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[CostRecordOut]:
    if assignment_id:
        require_visible_assignment(db, assignment_id, user)
    visible_ids = visible_request_ids(db, user)
    statement = select(CostRecord).order_by(CostRecord.freshness_at.desc())
    if assignment_id:
        statement = statement.where(CostRecord.assignment_id == assignment_id)
    elif visible_ids is not None:
        assignment_ids = select(ProviderAssignment.id).where(
            ProviderAssignment.request_id.in_(visible_ids)
        )
        statement = statement.where(CostRecord.assignment_id.in_(assignment_ids))
    records = db.scalars(statement.limit(200)).all()
    return [
        CostRecordOut(
            id=record.id,
            assignment_id=record.assignment_id,
            provider=record.provider,
            amount=record.amount,
            currency=record.currency,
            cost_type=record.cost_type,
            freshness_at=record.freshness_at,
        )
        for record in records
    ]


@budgets_router.get("", response_model=list[BudgetSummaryOut])
def list_budget_summaries(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[BudgetSummaryOut]:
    request_ids = visible_request_ids(db, user)
    request_statement = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if request_ids is not None:
        request_statement = request_statement.where(AccessRequest.id.in_(request_ids))
    requests = db.scalars(request_statement).all()
    summaries: list[BudgetSummaryOut] = []
    for access_request in requests:
        assignments = db.scalars(
            select(ProviderAssignment).where(ProviderAssignment.request_id == access_request.id)
        ).all()
        total_spend = Decimal("0")
        freshness_values = []
        for assignment in assignments:
            assignment_cost, _, freshness_at = assignment_totals(db, assignment.id)
            total_spend += assignment_cost
            if freshness_at:
                freshness_values.append(freshness_at)
        utilization = 0
        if access_request.requested_budget:
            utilization = int((total_spend / access_request.requested_budget) * 100)
        summaries.append(
            BudgetSummaryOut(
                request_id=access_request.id,
                project_name=access_request.project_name,
                requested_budget=access_request.requested_budget,
                total_spend=total_spend,
                remaining_budget=access_request.requested_budget - total_spend,
                utilization_percent=utilization,
                currency=access_request.currency,
                freshness_at=max(freshness_values) if freshness_values else None,
            )
        )
    return summaries

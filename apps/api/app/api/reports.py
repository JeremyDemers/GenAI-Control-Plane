import csv
from collections import Counter, defaultdict
from decimal import Decimal
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import AccessRequest, CostRecord, ProviderAssignment, UsageRecord, User
from app.models.enums import RequestStatus
from app.schemas import CostCenterSpendOut, ExecutiveReportOut, ProviderSpendOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/reports", tags=["reports"])

COST_ALLOCATION_EXPORT_FIELDS = [
    "cost_center",
    "project_name",
    "request_id",
    "assignment_id",
    "provider",
    "assignment_status",
    "currency",
    "requested_budget",
    "allocated_spend",
    "tokens",
    "request_count",
]


@router.get("/executive", response_model=ExecutiveReportOut)
def executive_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:executive")),
) -> ExecutiveReportOut:
    requests = db.scalars(select(AccessRequest)).all()
    assignments = db.scalars(select(ProviderAssignment)).all()
    costs = db.scalars(select(CostRecord)).all()
    usage = db.scalars(select(UsageRecord)).all()

    request_by_id = {request.id: request for request in requests}
    assignment_by_id = {assignment.id: assignment for assignment in assignments}
    total_budget = sum((request.requested_budget for request in requests), Decimal("0"))
    total_spend = sum((cost.amount for cost in costs), Decimal("0"))
    requests_by_status = Counter(request.status.value for request in requests)

    provider_spend: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    provider_tokens: dict[str, int] = defaultdict(int)
    active_assignments: Counter[str] = Counter()
    cost_center_budget: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    cost_center_spend: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for request in requests:
        cost_center_budget[request.cost_center] += request.requested_budget
    for assignment in assignments:
        if assignment.status == "active":
            active_assignments[assignment.provider] += 1
    for cost in costs:
        provider_spend[cost.provider] += cost.amount
        cost_assignment = assignment_by_id.get(cost.assignment_id)
        if cost_assignment:
            cost_request = request_by_id.get(cost_assignment.request_id)
            if cost_request:
                cost_center_spend[cost_request.cost_center] += cost.amount
    for record in usage:
        provider_tokens[record.provider] += record.tokens

    provider_names = set(provider_spend) | set(provider_tokens) | set(active_assignments)
    cost_centers = set(cost_center_budget) | set(cost_center_spend)

    return ExecutiveReportOut(
        total_requests=len(requests),
        active_projects=requests_by_status[RequestStatus.ACTIVE.value],
        pending_approvals=sum(
            requests_by_status[status.value]
            for status in (
                RequestStatus.AWAITING_MANAGER_APPROVAL,
                RequestStatus.AWAITING_SECURITY_REVIEW,
                RequestStatus.AWAITING_CTO_APPROVAL,
            )
        ),
        suspended_projects=requests_by_status[RequestStatus.SUSPENDED.value],
        total_budget=total_budget,
        total_spend=total_spend,
        remaining_budget=total_budget - total_spend,
        requests_by_status=dict(requests_by_status),
        spend_by_provider=[
            ProviderSpendOut(
                provider=provider,
                spend=provider_spend[provider],
                tokens=provider_tokens[provider],
                active_assignments=active_assignments[provider],
            )
            for provider in sorted(provider_names)
        ],
        spend_by_cost_center=[
            CostCenterSpendOut(
                cost_center=cost_center,
                budget=cost_center_budget[cost_center],
                spend=cost_center_spend[cost_center],
                remaining_budget=cost_center_budget[cost_center] - cost_center_spend[cost_center],
            )
            for cost_center in sorted(cost_centers)
        ],
    )


@router.get("/cost-allocation/export")
def export_cost_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:cost_export")),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    requests = db.scalars(select(AccessRequest)).all()
    assignments = db.scalars(select(ProviderAssignment)).all()
    costs = db.scalars(select(CostRecord)).all()
    usage = db.scalars(select(UsageRecord)).all()

    request_by_id = {request.id: request for request in requests}
    spend_by_assignment: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    tokens_by_assignment: dict[str, int] = defaultdict(int)
    calls_by_assignment: dict[str, int] = defaultdict(int)

    for cost in costs:
        spend_by_assignment[cost.assignment_id] += cost.amount
    for record in usage:
        tokens_by_assignment[record.assignment_id] += record.tokens
        calls_by_assignment[record.assignment_id] += record.request_count

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=COST_ALLOCATION_EXPORT_FIELDS)
    writer.writeheader()
    row_count = 0
    for assignment in sorted(assignments, key=lambda item: (item.provider, item.id)):
        request = request_by_id.get(assignment.request_id)
        if request is None:
            continue
        writer.writerow(
            {
                "cost_center": request.cost_center,
                "project_name": request.project_name,
                "request_id": request.id,
                "assignment_id": assignment.id,
                "provider": assignment.provider,
                "assignment_status": assignment.status,
                "currency": request.currency,
                "requested_budget": request.requested_budget,
                "allocated_spend": spend_by_assignment[assignment.id],
                "tokens": tokens_by_assignment[assignment.id],
                "request_count": calls_by_assignment[assignment.id],
            }
        )
        row_count += 1

    record_audit_event(
        db,
        event_type="report.cost_allocation_exported",
        actor_user_id=user.id,
        target_type="cost_allocation_report",
        target_id=None,
        action="export",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"format": "csv", "row_count": row_count},
    )
    db.commit()
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cost-allocation.csv"'},
    )

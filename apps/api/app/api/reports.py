from collections import Counter, defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.database import get_db
from app.models.entities import AccessRequest, CostRecord, ProviderAssignment, UsageRecord, User
from app.models.enums import RequestStatus
from app.schemas import CostCenterSpendOut, ExecutiveReportOut, ProviderSpendOut

router = APIRouter(prefix="/reports", tags=["reports"])


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

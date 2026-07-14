import csv
from collections import defaultdict
from decimal import Decimal
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AccessRequest, CostRecord, ProviderAssignment, UsageRecord

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


def cost_allocation_csv(db: Session) -> tuple[str, int]:
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
    return output.getvalue(), row_count

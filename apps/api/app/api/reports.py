import csv
from collections import Counter, defaultdict
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import (
    AccessRequest,
    CostRecord,
    LifecycleJob,
    ProviderAssignment,
    UsageRecord,
    User,
)
from app.models.enums import RequestStatus
from app.schemas import (
    CostAllocationDeliveryCreate,
    CostAllocationDeliveryOut,
    CostCenterSpendOut,
    ExecutiveReportOut,
    ProviderSpendOut,
)
from app.services.audit import record_audit_event
from app.services.reports import cost_allocation_csv
from app.workers.jobs import run_queued_lifecycle_jobs

router = APIRouter(prefix="/reports", tags=["reports"])


def delivery_out(job: LifecycleJob) -> CostAllocationDeliveryOut:
    metadata = job.payload or job.failure_information or {}
    return CostAllocationDeliveryOut(
        id=job.id,
        status=job.status,
        frequency=str(metadata.get("frequency", "weekly")),
        recipients=[str(recipient) for recipient in metadata.get("recipients", [])],
        row_count=int(metadata.get("row_count", 0)),
        created_at=job.created_at,
    )


def build_executive_report(db: Session) -> ExecutiveReportOut:
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


@router.get("/executive", response_model=ExecutiveReportOut)
def executive_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:executive")),
) -> ExecutiveReportOut:
    return build_executive_report(db)


@router.get("/executive/export")
def export_executive_report(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:executive")),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    report = build_executive_report(db)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "name", "metric", "value"])
    writer.writerow(["summary", "total_requests", "count", report.total_requests])
    writer.writerow(["summary", "active_projects", "count", report.active_projects])
    writer.writerow(["summary", "pending_approvals", "count", report.pending_approvals])
    writer.writerow(["summary", "suspended_projects", "count", report.suspended_projects])
    writer.writerow(["summary", "total_budget", "amount", report.total_budget])
    writer.writerow(["summary", "total_spend", "amount", report.total_spend])
    writer.writerow(["summary", "remaining_budget", "amount", report.remaining_budget])
    for status, count in sorted(report.requests_by_status.items()):
        writer.writerow(["request_status", status, "count", count])
    for provider in report.spend_by_provider:
        writer.writerow(["provider", provider.provider, "spend", provider.spend])
        writer.writerow(["provider", provider.provider, "tokens", provider.tokens])
        writer.writerow(
            ["provider", provider.provider, "active_assignments", provider.active_assignments]
        )
    for cost_center in report.spend_by_cost_center:
        writer.writerow(["cost_center", cost_center.cost_center, "budget", cost_center.budget])
        writer.writerow(["cost_center", cost_center.cost_center, "spend", cost_center.spend])
        writer.writerow(
            [
                "cost_center",
                cost_center.cost_center,
                "remaining_budget",
                cost_center.remaining_budget,
            ]
        )
    row_count = len(output.getvalue().splitlines()) - 1

    record_audit_event(
        db,
        event_type="report.executive_exported",
        actor_user_id=user.id,
        target_type="executive_report",
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
        headers={"Content-Disposition": 'attachment; filename="executive-report.csv"'},
    )


@router.get("/cost-allocation/export")
def export_cost_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:cost_export")),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    content, row_count = cost_allocation_csv(db)

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
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cost-allocation.csv"'},
    )


@router.get("/cost-allocation/deliveries", response_model=list[CostAllocationDeliveryOut])
def list_cost_allocation_deliveries(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:cost_export")),
) -> list[CostAllocationDeliveryOut]:
    jobs = db.scalars(
        select(LifecycleJob)
        .where(LifecycleJob.job_type == "cost_allocation_delivery")
        .order_by(LifecycleJob.created_at.desc())
        .limit(50)
    ).all()
    return [delivery_out(job) for job in jobs]


@router.post(
    "/cost-allocation/deliveries",
    response_model=CostAllocationDeliveryOut,
    status_code=201,
)
async def schedule_cost_allocation_delivery(
    payload: CostAllocationDeliveryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:schedule")),
    correlation_id: str = Depends(get_correlation_id),
) -> CostAllocationDeliveryOut:
    job = LifecycleJob(
        job_type="cost_allocation_delivery",
        status="queued",
        attempt_count=0,
        idempotency_key=f"report-delivery:{uuid4()}",
        payload={
            "frequency": payload.frequency,
            "recipients": payload.recipients,
            "row_count": 0,
            "format": "csv",
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    record_audit_event(
        db,
        event_type="report.cost_allocation_delivery_scheduled",
        actor_user_id=user.id,
        target_type="lifecycle_job",
        target_id=job.id,
        action="schedule_delivery",
        result="queued",
        correlation_id=correlation_id,
        metadata_json={
            "frequency": payload.frequency,
            "recipients": payload.recipients,
        },
    )
    if get_settings().lifecycle_inline_execution:
        await run_queued_lifecycle_jobs(db, limit=1)
    db.commit()
    db.refresh(job)
    return delivery_out(job)

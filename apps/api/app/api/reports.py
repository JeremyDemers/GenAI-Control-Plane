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
    Project,
    ProjectMember,
    ProviderAssignment,
    UsageRecord,
    User,
)
from app.models.enums import RequestStatus
from app.schemas import (
    AdoptionDimensionOut,
    AdoptionReportOut,
    CostAllocationDeliveryCreate,
    CostAllocationDeliveryOut,
    CostCenterSpendOut,
    ExecutiveReportOut,
    ProjectAdoptionOut,
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


def build_adoption_report(db: Session) -> AdoptionReportOut:
    users = db.scalars(select(User)).all()
    requests = db.scalars(select(AccessRequest)).all()
    projects = db.scalars(select(Project)).all()
    members = db.scalars(select(ProjectMember)).all()
    assignments = db.scalars(select(ProviderAssignment)).all()
    usage = db.scalars(select(UsageRecord)).all()
    costs = db.scalars(select(CostRecord)).all()

    users_by_id = {user.id: user for user in users}
    requests_by_id = {request.id: request for request in requests}
    projects_by_id = {project.id: project for project in projects}

    usage_by_assignment: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    cost_by_assignment: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for usage_record in usage:
        tokens, request_events = usage_by_assignment[usage_record.assignment_id]
        usage_by_assignment[usage_record.assignment_id] = (
            tokens + usage_record.tokens,
            request_events + usage_record.request_count,
        )
    for cost_record in costs:
        cost_by_assignment[cost_record.assignment_id] += cost_record.amount

    department_requests: Counter[str] = Counter()
    department_active_assignments: Counter[str] = Counter()
    department_tokens: Counter[str] = Counter()
    department_request_events: Counter[str] = Counter()
    department_spend: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    provider_requests: Counter[str] = Counter()
    provider_active_assignments: Counter[str] = Counter()
    provider_tokens: Counter[str] = Counter()
    provider_request_events: Counter[str] = Counter()
    provider_spend: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    project_request_count: Counter[str | None] = Counter()
    project_active_assignments: Counter[str | None] = Counter()
    project_tokens: Counter[str | None] = Counter()
    project_spend: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    project_member_count: Counter[str] = Counter(member.project_id for member in members)

    for request in requests:
        requester = users_by_id.get(request.requester_id)
        department = requester.department if requester else "Unknown"
        department_requests[department] += 1
        project_request_count[request.project_id] += 1
        for provider in request.provider_names:
            provider_requests[provider] += 1

    for assignment in assignments:
        assignment_request = requests_by_id.get(assignment.request_id)
        requester = users_by_id.get(assignment_request.requester_id) if assignment_request else None
        department = requester.department if requester else "Unknown"
        project_id = assignment.project_id or (
            assignment_request.project_id if assignment_request else None
        )
        tokens, request_events = usage_by_assignment[assignment.id]
        spend = cost_by_assignment[assignment.id]

        if assignment.status == "active":
            department_active_assignments[department] += 1
            provider_active_assignments[assignment.provider] += 1
            project_active_assignments[project_id] += 1
        department_tokens[department] += tokens
        department_request_events[department] += request_events
        department_spend[department] += spend
        provider_tokens[assignment.provider] += tokens
        provider_request_events[assignment.provider] += request_events
        provider_spend[assignment.provider] += spend
        project_tokens[project_id] += tokens
        project_spend[project_id] += spend

    departments = set(department_requests) | set(department_tokens) | set(department_spend)
    providers = set(provider_requests) | set(provider_tokens) | set(provider_spend)
    project_ids = set(project_request_count) | set(project_tokens) | set(project_spend)

    projects_with_usage: set[str | None] = set()
    for assignment in assignments:
        if usage_by_assignment[assignment.id][0] <= 0:
            continue
        assignment_request = requests_by_id.get(assignment.request_id)
        projects_with_usage.add(
            assignment.project_id or (assignment_request.project_id if assignment_request else None)
        )

    project_activity: list[ProjectAdoptionOut] = []
    for project_id in sorted(project_ids, key=lambda value: value or ""):
        project = projects_by_id.get(project_id) if project_id else None
        owner_email = None
        if project and project.owner_user_id:
            owner = users_by_id.get(project.owner_user_id)
            owner_email = owner.email if owner else None
        project_activity.append(
            ProjectAdoptionOut(
                project_id=project_id,
                project_name=project.name if project else "Unassigned",
                owner_email=owner_email,
                cost_center=project.cost_center if project else "Unassigned",
                member_count=project_member_count[project_id] if project_id else 0,
                request_count=project_request_count[project_id],
                active_assignments=project_active_assignments[project_id],
                total_tokens=project_tokens[project_id],
                total_spend=project_spend[project_id],
            )
        )

    return AdoptionReportOut(
        total_users=len(users),
        users_with_requests=len({request.requester_id for request in requests}),
        projects_with_usage=len(projects_with_usage),
        active_assignments=sum(1 for assignment in assignments if assignment.status == "active"),
        total_tokens=sum(record.tokens for record in usage),
        total_request_events=sum(record.request_count for record in usage),
        total_spend=sum((record.amount for record in costs), Decimal("0")),
        adoption_by_department=[
            AdoptionDimensionOut(
                name=department,
                request_count=department_requests[department],
                active_assignments=department_active_assignments[department],
                total_tokens=department_tokens[department],
                total_request_events=department_request_events[department],
                total_spend=department_spend[department],
            )
            for department in sorted(departments)
        ],
        adoption_by_provider=[
            AdoptionDimensionOut(
                name=provider,
                request_count=provider_requests[provider],
                active_assignments=provider_active_assignments[provider],
                total_tokens=provider_tokens[provider],
                total_request_events=provider_request_events[provider],
                total_spend=provider_spend[provider],
            )
            for provider in sorted(providers)
        ],
        project_activity=project_activity,
    )


@router.get("/executive", response_model=ExecutiveReportOut)
def executive_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:executive")),
) -> ExecutiveReportOut:
    return build_executive_report(db)


@router.get("/adoption", response_model=AdoptionReportOut)
def adoption_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:adoption")),
) -> AdoptionReportOut:
    return build_adoption_report(db)


@router.get("/adoption/export")
def export_adoption_report(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:adoption")),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    report = build_adoption_report(db)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "name", "metric", "value"])
    writer.writerow(["summary", "total_users", "count", report.total_users])
    writer.writerow(["summary", "users_with_requests", "count", report.users_with_requests])
    writer.writerow(["summary", "projects_with_usage", "count", report.projects_with_usage])
    writer.writerow(["summary", "active_assignments", "count", report.active_assignments])
    writer.writerow(["summary", "total_tokens", "count", report.total_tokens])
    writer.writerow(["summary", "total_request_events", "count", report.total_request_events])
    writer.writerow(["summary", "total_spend", "amount", report.total_spend])
    for department in report.adoption_by_department:
        writer.writerow(["department", department.name, "request_count", department.request_count])
        writer.writerow(
            ["department", department.name, "active_assignments", department.active_assignments]
        )
        writer.writerow(["department", department.name, "total_tokens", department.total_tokens])
        writer.writerow(["department", department.name, "total_spend", department.total_spend])
    for provider in report.adoption_by_provider:
        writer.writerow(["provider", provider.name, "request_count", provider.request_count])
        writer.writerow(
            ["provider", provider.name, "active_assignments", provider.active_assignments]
        )
        writer.writerow(["provider", provider.name, "total_tokens", provider.total_tokens])
        writer.writerow(["provider", provider.name, "total_spend", provider.total_spend])
    for project in report.project_activity:
        writer.writerow(["project", project.project_name, "cost_center", project.cost_center])
        writer.writerow(["project", project.project_name, "member_count", project.member_count])
        writer.writerow(["project", project.project_name, "request_count", project.request_count])
        writer.writerow(
            ["project", project.project_name, "active_assignments", project.active_assignments]
        )
        writer.writerow(["project", project.project_name, "total_tokens", project.total_tokens])
        writer.writerow(["project", project.project_name, "total_spend", project.total_spend])
    row_count = len(output.getvalue().splitlines()) - 1

    record_audit_event(
        db,
        event_type="report.adoption_exported",
        actor_user_id=user.id,
        target_type="adoption_report",
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
        headers={"Content-Disposition": 'attachment; filename="adoption-report.csv"'},
    )


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

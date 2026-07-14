from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.access_requests import to_request_out
from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import AccessRequest, ApprovalDecision, ApprovalStep, User
from app.models.enums import RequestStatus
from app.schemas import AccessRequestOut, ApprovalAction, ApprovalHistoryOut, CtoOverrideIn
from app.services.audit import record_audit_event
from app.services.notifications import notify_approval_step, notify_user
from app.services.state_machine import transition
from app.workers.jobs import provision_request

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/pending")
def pending_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("approvals:review")),
) -> list[dict[str, str]]:
    role_names = {role.name for role in user.roles}
    statement = select(ApprovalStep).where(ApprovalStep.status == "pending")
    role_map = {
        "approver": "approver",
        "security_reviewer": "security_reviewer",
        "cto": "cto",
    }
    allowed_roles = {role_map[role] for role in role_names if role in role_map}
    if allowed_roles:
        statement = statement.where(ApprovalStep.assigned_role.in_(allowed_roles))
    steps = db.scalars(statement).all()
    return [
        {
            "step_id": step.id,
            "request_id": step.request_id,
            "step_type": step.step_type,
            "assigned_role": step.assigned_role,
        }
        for step in steps
    ]


@router.get("/history", response_model=list[ApprovalHistoryOut])
def approval_history(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("requests:read_all")),
) -> list[ApprovalHistoryOut]:
    rows = db.execute(
        select(ApprovalStep, AccessRequest, ApprovalDecision, User)
        .join(AccessRequest, AccessRequest.id == ApprovalStep.request_id)
        .outerjoin(ApprovalDecision, ApprovalDecision.approval_step_id == ApprovalStep.id)
        .outerjoin(User, User.id == ApprovalDecision.actor_user_id)
        .order_by(
            AccessRequest.created_at.desc(),
            ApprovalStep.sequence.asc(),
            ApprovalDecision.created_at.asc(),
        )
    ).all()
    return [
        ApprovalHistoryOut(
            approval_step_id=step.id,
            request_id=request.id,
            project_name=request.project_name,
            step_type=step.step_type,
            assigned_role=step.assigned_role,
            step_status=step.status,
            decision_id=decision.id if decision else None,
            decision=decision.decision if decision else None,
            comments=decision.comments if decision else "",
            actor_email=actor.email if actor else None,
            decided_at=decision.created_at if decision else None,
            step_created_at=step.created_at,
        )
        for step, request, decision, actor in rows
    ]


@router.post("/override/{request_id}", response_model=AccessRequestOut)
async def cto_override(
    request_id: str,
    payload: CtoOverrideIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("approvals:cto")),
    correlation_id: str = Depends(get_correlation_id),
) -> AccessRequestOut:
    request = db.get(AccessRequest, request_id)
    if not request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request not found."}
        )
    if request.status in {
        RequestStatus.ACTIVE,
        RequestStatus.EXPIRING_SOON,
        RequestStatus.SUSPENDED,
        RequestStatus.EXPIRED,
        RequestStatus.ARCHIVING,
        RequestStatus.CLOSED,
        RequestStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REQUEST_NOT_OVERRIDABLE",
                "message": "Only pending, failed, or rejected approval requests can be overridden.",
            },
        )

    steps = db.scalars(
        select(ApprovalStep)
        .where(ApprovalStep.request_id == request.id)
        .order_by(ApprovalStep.sequence.asc())
    ).all()
    if not steps:
        raise HTTPException(
            status_code=400,
            detail={"code": "REQUEST_NOT_OVERRIDABLE", "message": "No approval steps found."},
        )
    override_decision = f"override_{payload.decision}"
    for step in steps:
        if step.status not in {"approve", "reject"}:
            step.status = "overridden"
        db.add(
            ApprovalDecision(
                approval_step_id=step.id,
                actor_user_id=user.id,
                decision=override_decision,
                comments=payload.justification,
            )
        )

    if payload.decision == "reject":
        request.status = RequestStatus.REJECTED
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="approval_overridden",
            message=f"{request.project_name} was rejected by CTO override.",
        )
    else:
        request.status = RequestStatus.APPROVED
        request.approved_at = datetime.now(UTC)
        await provision_request(db, request, correlation_id)
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="approval_overridden",
            message=f"{request.project_name} was approved by CTO override.",
        )

    record_audit_event(
        db,
        event_type="approval.override",
        actor_user_id=user.id,
        target_type="access_request",
        target_id=request.id,
        request_id=request.id,
        action=override_decision,
        result="success",
        reason=payload.justification,
        correlation_id=correlation_id,
        project_id=request.project_id,
    )
    db.commit()
    db.refresh(request)
    return to_request_out(request)


@router.post("/{step_id}", response_model=AccessRequestOut)
async def decide(
    step_id: str,
    payload: ApprovalAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("approvals:review")),
    correlation_id: str = Depends(get_correlation_id),
) -> AccessRequestOut:
    step = db.get(ApprovalStep, step_id)
    if not step or step.status != "pending":
        raise HTTPException(
            status_code=400,
            detail={"code": "REQUEST_NOT_APPROVABLE", "message": "Approval step is not pending."},
        )
    request = db.get(AccessRequest, step.request_id)
    if not request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request not found."}
        )

    role_names = {role.name for role in user.roles}
    if step.assigned_role not in role_names:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Approval step is assigned to another role."},
        )

    step.status = payload.decision
    db.add(
        ApprovalDecision(
            approval_step_id=step.id,
            actor_user_id=user.id,
            decision=payload.decision,
            comments=payload.comments,
        )
    )
    next_step = None
    if payload.decision == "reject":
        request.status = transition(request.status, RequestStatus.REJECTED)
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="request_rejected",
            message=f"{request.project_name} was rejected during approval.",
        )
    elif payload.decision == "request_information":
        request.status = transition(request.status, RequestStatus.SUBMITTED)
        notify_user(
            db,
            user_id=request.requester_id,
            event_type="request_information_requested",
            message=f"{request.project_name} needs more information before approval can continue.",
        )
    else:
        db.flush()
        next_step = db.scalar(
            select(ApprovalStep)
            .where(ApprovalStep.request_id == request.id, ApprovalStep.status == "pending")
            .order_by(ApprovalStep.sequence)
        )
        if next_step:
            desired = {
                "manager": RequestStatus.AWAITING_MANAGER_APPROVAL,
                "security": RequestStatus.AWAITING_SECURITY_REVIEW,
                "cto": RequestStatus.AWAITING_CTO_APPROVAL,
            }[next_step.step_type]
            if desired != request.status:
                request.status = transition(request.status, desired)
            notify_approval_step(
                db,
                step_type=next_step.step_type,
                project_name=request.project_name,
                request_id=request.id,
            )
        else:
            request.status = transition(request.status, RequestStatus.APPROVED)
            request.approved_at = datetime.now(UTC)
            await provision_request(db, request, correlation_id)
            notify_user(
                db,
                user_id=request.requester_id,
                event_type="request_provisioned",
                message=f"{request.project_name} was approved and provisioned.",
            )

    record_audit_event(
        db,
        event_type="approval.decision",
        actor_user_id=user.id,
        target_type="approval_step",
        target_id=step.id,
        request_id=request.id,
        action=payload.decision,
        result="success",
        correlation_id=correlation_id,
        metadata_json={"comments": payload.comments},
    )
    db.commit()
    db.refresh(request)
    return to_request_out(request)

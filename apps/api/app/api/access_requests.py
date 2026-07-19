from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import (
    AccessRequest,
    ApprovalStep,
    PolicyEvaluation,
    Project,
    ProjectMember,
    User,
)
from app.models.enums import RequestStatus, canonical_provider_values
from app.schemas import (
    AccessRequestCreate,
    AccessRequestOut,
    AdditionalInformationIn,
    PolicyEvaluationOut,
)
from app.services.audit import record_audit_event
from app.services.notifications import notify_approval_step, notify_user
from app.services.policies import evaluate_request
from app.services.state_machine import transition
from app.services.visibility import visible_request_ids

router = APIRouter(prefix="/access-requests", tags=["access requests"])


def to_request_out(request: AccessRequest) -> AccessRequestOut:
    return AccessRequestOut(
        id=request.id,
        project_id=request.project_id,
        project_name=request.project_name,
        requester_id=request.requester_id,
        status=request.status,
        business_justification=request.business_justification,
        data_classification=request.data_classification,
        requested_budget=request.requested_budget,
        currency=request.currency,
        provider_names=canonical_provider_values(request.provider_names),
        requested_start_at=request.requested_start_at,
        requested_end_at=request.requested_end_at,
        submitted_at=request.submitted_at,
        expires_at=request.expires_at,
    )


@router.get("", response_model=list[AccessRequestOut])
def list_requests(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AccessRequestOut]:
    statement = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    request_ids = visible_request_ids(db, user)
    if request_ids is not None:
        statement = statement.where(AccessRequest.id.in_(request_ids))
    return [to_request_out(request) for request in db.scalars(statement).all()]


@router.post("", response_model=AccessRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("requests:create")),
    correlation_id: str = Depends(get_correlation_id),
) -> AccessRequestOut:
    collaborators = db.scalars(
        select(User).where(User.email.in_(payload.requested_collaborators))
    ).all()
    project_owner = next(
        (
            collaborator
            for collaborator in collaborators
            if any(role.name == "project_owner" for role in collaborator.roles)
        ),
        user,
    )
    project = Project(
        name=payload.project_name,
        cost_center=payload.cost_center,
        owner_user_id=project_owner.id,
        status="active",
    )
    db.add(project)
    db.flush()

    request = AccessRequest(
        requester_id=user.id,
        project_id=project.id,
        project_name=payload.project_name,
        project_sponsor=payload.project_sponsor,
        cost_center=payload.cost_center,
        business_justification=payload.business_justification,
        data_classification=payload.data_classification,
        requested_start_at=payload.requested_start_at,
        requested_end_at=payload.requested_end_at,
        requested_budget=payload.requested_budget,
        currency=payload.currency.upper(),
        expected_users=payload.expected_users,
        requested_collaborators=payload.requested_collaborators,
        provider_names=canonical_provider_values(
            [provider.value for provider in payload.requested_providers]
        ),
        requested_services=payload.requested_services,
        uses_pii=payload.uses_pii,
        uses_confidential_data=payload.uses_confidential_data,
        uses_regulated_data=payload.uses_regulated_data,
        uses_source_code=payload.uses_source_code,
        expected_artifacts=payload.expected_artifacts,
        expected_usage_pattern=payload.expected_usage_pattern,
        estimated_monthly_volume=payload.estimated_monthly_volume,
        additional_notes=payload.additional_notes,
        status=RequestStatus.DRAFT,
    )
    request.status = transition(request.status, RequestStatus.SUBMITTED)
    request.submitted_at = datetime.now(UTC)
    db.add(request)
    db.flush()
    members_by_id: dict[str, ProjectMember] = {}
    for member_user, member_role in [
        (user, "owner" if project_owner.id == user.id else "requester"),
        *[
            (
                collaborator,
                "owner" if collaborator.id == project_owner.id else "collaborator",
            )
            for collaborator in collaborators
        ],
    ]:
        if member_user.id in members_by_id:
            continue
        member = ProjectMember(
            project_id=project.id,
            user_id=member_user.id,
            member_role=member_role,
        )
        members_by_id[member_user.id] = member
        db.add(member)

    evaluation = evaluate_request(db, request)
    if evaluation.final_decision == "denied":
        request.status = RequestStatus.REJECTED
    else:
        first_step = evaluation.approval_path[0]
        request.status = transition(
            request.status,
            {
                "manager": RequestStatus.AWAITING_MANAGER_APPROVAL,
                "security": RequestStatus.AWAITING_SECURITY_REVIEW,
                "cto": RequestStatus.AWAITING_CTO_APPROVAL,
            }[first_step],
        )

    for sequence, step in enumerate(evaluation.approval_path, start=1):
        db.add(
            ApprovalStep(
                request_id=request.id,
                step_type=step,
                assigned_role={
                    "manager": "approver",
                    "security": "security_reviewer",
                    "cto": "cto",
                }[step],
                sequence=sequence,
            )
        )

    notify_user(
        db,
        user_id=user.id,
        event_type="request_submitted",
        message=f"{request.project_name} was submitted for governed AI access.",
    )
    if evaluation.final_decision != "denied":
        notify_approval_step(
            db,
            step_type=evaluation.approval_path[0],
            project_name=request.project_name,
            request_id=request.id,
        )
    for collaborator in collaborators:
        notify_user(
            db,
            user_id=collaborator.id,
            event_type="project_member_added",
            message=f"You were added to {request.project_name}.",
        )

    record_audit_event(
        db,
        event_type="access_request.submitted",
        actor_user_id=user.id,
        target_type="access_request",
        target_id=request.id,
        request_id=request.id,
        project_id=project.id,
        action="submit",
        result="success",
        correlation_id=correlation_id,
        metadata_json={
            "approval_path": evaluation.approval_path,
            "project_id": project.id,
            "collaborators": [collaborator.email for collaborator in collaborators],
        },
    )
    db.commit()
    db.refresh(request)
    return to_request_out(request)


@router.post("/{request_id}/cancel", response_model=AccessRequestOut)
def cancel_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("requests:cancel_own")),
    correlation_id: str = Depends(get_correlation_id),
) -> AccessRequestOut:
    request = db.get(AccessRequest, request_id)
    if not request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request not found."}
        )
    if request.requester_id != user.id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Only the requester can cancel this request."},
        )
    if request.status not in {
        RequestStatus.SUBMITTED,
        RequestStatus.AWAITING_MANAGER_APPROVAL,
        RequestStatus.AWAITING_SECURITY_REVIEW,
        RequestStatus.AWAITING_CTO_APPROVAL,
        RequestStatus.APPROVED,
        RequestStatus.PROVISIONING_FAILED,
    }:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REQUEST_NOT_CANCELLABLE",
                "message": "Only pending or failed provisioning requests can be cancelled.",
            },
        )
    request.status = transition(request.status, RequestStatus.CANCELLED)
    pending_steps = db.scalars(
        select(ApprovalStep).where(
            ApprovalStep.request_id == request.id,
            ApprovalStep.status == "pending",
        )
    ).all()
    for step in pending_steps:
        step.status = "cancelled"
    notify_user(
        db,
        user_id=user.id,
        event_type="request_cancelled",
        message=f"{request.project_name} was cancelled.",
    )
    record_audit_event(
        db,
        event_type="access_request.cancelled",
        actor_user_id=user.id,
        target_type="access_request",
        target_id=request.id,
        request_id=request.id,
        action="cancel",
        result="success",
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(request)
    return to_request_out(request)


@router.post("/{request_id}/information-response", response_model=AccessRequestOut)
def respond_to_information_request(
    request_id: str,
    payload: AdditionalInformationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("requests:create")),
    correlation_id: str = Depends(get_correlation_id),
) -> AccessRequestOut:
    request = db.get(AccessRequest, request_id)
    if not request:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Request not found."}
        )
    if request.requester_id != user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Only the requester can provide additional information.",
            },
        )
    step = db.scalar(
        select(ApprovalStep)
        .where(
            ApprovalStep.request_id == request.id,
            ApprovalStep.status == "request_information",
        )
        .order_by(ApprovalStep.sequence)
    )
    if request.status != RequestStatus.SUBMITTED or not step:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INFORMATION_NOT_REQUESTED",
                "message": "This request is not waiting for additional information.",
            },
        )

    request.additional_notes = (
        f"{request.additional_notes}\nAdditional information: {payload.response}".strip()
    )
    step.status = "pending"
    request.status = transition(
        request.status,
        {
            "manager": RequestStatus.AWAITING_MANAGER_APPROVAL,
            "security": RequestStatus.AWAITING_SECURITY_REVIEW,
            "cto": RequestStatus.AWAITING_CTO_APPROVAL,
        }[step.step_type],
    )
    notify_approval_step(
        db,
        step_type=step.step_type,
        project_name=request.project_name,
        request_id=request.id,
    )
    record_audit_event(
        db,
        event_type="access_request.information_provided",
        actor_user_id=user.id,
        target_type="access_request",
        target_id=request.id,
        request_id=request.id,
        project_id=request.project_id,
        action="provide_information",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"response": payload.response},
    )
    db.commit()
    db.refresh(request)
    return to_request_out(request)


@router.get("/{request_id}/policy-evaluation", response_model=PolicyEvaluationOut)
def get_policy_evaluation(
    request_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> PolicyEvaluationOut:
    evaluation = db.scalar(
        select(PolicyEvaluation)
        .where(PolicyEvaluation.request_id == request_id)
        .order_by(PolicyEvaluation.evaluated_at.desc())
    )
    if not evaluation:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "No evaluation"}
        )
    return PolicyEvaluationOut(
        id=evaluation.id,
        request_id=evaluation.request_id,
        policy_version_id=evaluation.policy_version_id,
        triggered_rules=evaluation.triggered_rules,
        approval_path=evaluation.approval_path,
        restrictions=evaluation.restrictions,
        final_decision=evaluation.final_decision,
        evaluated_at=evaluation.evaluated_at,
    )

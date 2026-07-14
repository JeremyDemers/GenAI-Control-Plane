from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import AccessRequest, ApprovalStep, PolicyEvaluation, User
from app.models.enums import RequestStatus
from app.schemas import AccessRequestCreate, AccessRequestOut, PolicyEvaluationOut
from app.services.audit import record_audit_event
from app.services.policies import evaluate_request
from app.services.state_machine import transition

router = APIRouter(prefix="/access-requests", tags=["access requests"])


def to_request_out(request: AccessRequest) -> AccessRequestOut:
    return AccessRequestOut(
        id=request.id,
        project_name=request.project_name,
        requester_id=request.requester_id,
        status=request.status,
        business_justification=request.business_justification,
        data_classification=request.data_classification,
        requested_budget=request.requested_budget,
        currency=request.currency,
        provider_names=request.provider_names,
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
    role_names = {role.name for role in user.roles}
    statement = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if (
        "platform_admin" not in role_names
        and "security_auditor" not in role_names
        and "cto" not in role_names
    ):
        statement = statement.where(AccessRequest.requester_id == user.id)
    return [to_request_out(request) for request in db.scalars(statement).all()]


@router.post("", response_model=AccessRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("requests:create")),
    correlation_id: str = Depends(get_correlation_id),
) -> AccessRequestOut:
    request = AccessRequest(
        requester_id=user.id,
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
        provider_names=[provider.value for provider in payload.requested_providers],
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

    record_audit_event(
        db,
        event_type="access_request.submitted",
        actor_user_id=user.id,
        target_type="access_request",
        target_id=request.id,
        request_id=request.id,
        action="submit",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"approval_path": evaluation.approval_path},
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
        triggered_rules=evaluation.triggered_rules,
        approval_path=evaluation.approval_path,
        restrictions=evaluation.restrictions,
        final_decision=evaluation.final_decision,
        evaluated_at=evaluation.evaluated_at,
    )

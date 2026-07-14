from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import PolicyDefinition, PolicyVersion, User
from app.schemas import PolicyVersionCreate, PolicyVersionOut
from app.services.audit import record_audit_event
from app.services.policies import STANDARD_POLICY, ensure_standard_policy

router = APIRouter(prefix="/policies", tags=["policies"])


REQUIRED_POLICY_KEYS = {
    "maximum_duration_days",
    "maximum_budget_usd",
    "approval_rules",
    "budget",
    "actions",
    "prohibited_data_classes",
}


def policy_out(definition: PolicyDefinition, version: PolicyVersion) -> PolicyVersionOut:
    return PolicyVersionOut(
        id=version.id,
        policy_definition_id=definition.id,
        name=definition.name,
        description=definition.description,
        version=version.version,
        document=version.document,
        active=version.active,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


@router.get("", response_model=list[PolicyVersionOut])
def list_policy_versions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("policy_evaluations:read")),
) -> list[PolicyVersionOut]:
    ensure_standard_policy(db)
    rows = db.execute(
        select(PolicyDefinition, PolicyVersion)
        .join(PolicyVersion, PolicyVersion.policy_definition_id == PolicyDefinition.id)
        .order_by(PolicyDefinition.name, PolicyVersion.version.desc())
    ).all()
    return [policy_out(definition, version) for definition, version in rows]


@router.post("/standard-ai-sandbox/versions", response_model=PolicyVersionOut, status_code=201)
def publish_standard_policy_version(
    payload: PolicyVersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("policies:manage")),
    correlation_id: str = Depends(get_correlation_id),
) -> PolicyVersionOut:
    base_document = deepcopy(STANDARD_POLICY)
    document = {**base_document, **payload.document, "name": "standard-ai-sandbox"}
    missing_keys = REQUIRED_POLICY_KEYS - set(document)
    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_POLICY_DOCUMENT",
                "message": f"Missing policy keys: {', '.join(sorted(missing_keys))}",
            },
        )
    definition = db.scalar(
        select(PolicyDefinition).where(PolicyDefinition.name == "standard-ai-sandbox")
    )
    if not definition:
        ensure_standard_policy(db)
        definition = db.scalar(
            select(PolicyDefinition).where(PolicyDefinition.name == "standard-ai-sandbox")
        )
    if not definition:
        raise HTTPException(
            status_code=500,
            detail={"code": "POLICY_DEFINITION_MISSING", "message": "Policy definition missing."},
        )
    latest_version = db.scalar(
        select(func.coalesce(func.max(PolicyVersion.version), 0)).where(
            PolicyVersion.policy_definition_id == definition.id
        )
    )
    active_versions = db.scalars(
        select(PolicyVersion).where(
            PolicyVersion.policy_definition_id == definition.id,
            PolicyVersion.active.is_(True),
        )
    ).all()
    for version in active_versions:
        version.active = False
    next_version = int(latest_version or 0) + 1
    document["version"] = next_version
    version = PolicyVersion(
        policy_definition_id=definition.id,
        version=next_version,
        document=document,
        active=True,
    )
    if payload.description:
        definition.description = payload.description
    db.add(version)
    db.flush()
    record_audit_event(
        db,
        event_type="policy.version_published",
        actor_user_id=user.id,
        target_type="policy_version",
        target_id=version.id,
        action="publish",
        result="success",
        correlation_id=correlation_id,
        metadata_json={"policy": definition.name, "version": next_version},
    )
    db.commit()
    db.refresh(version)
    return policy_out(definition, version)

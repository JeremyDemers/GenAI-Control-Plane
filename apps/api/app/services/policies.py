from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AccessRequest, PolicyDefinition, PolicyEvaluation, PolicyVersion
from app.models.enums import DataClassification

STANDARD_POLICY = {
    "name": "standard-ai-sandbox",
    "version": 1,
    "maximum_duration_days": 30,
    "maximum_budget_usd": 1000,
    "artifact_retention_days": 365,
    "approval_rules": {
        "require_manager_approval": True,
        "require_security_review_for": ["confidential", "regulated"],
        "require_cto_approval_when": {
            "requested_budget_greater_than": 500,
            "high_risk_provider_requested": True,
        },
    },
    "budget": {"warning_percent": 70, "critical_percent": 90, "enforcement_percent": 100},
    "actions": {
        "warning": ["notify_requester", "notify_project_owner"],
        "critical": ["notify_platform_admin", "restrict_high_cost_models"],
        "enforcement": ["suspend_access", "revoke_credentials", "create_incident"],
    },
    "prohibited_data_classes": ["restricted"],
}


def ensure_standard_policy(db: Session) -> PolicyVersion:
    existing = db.scalar(
        select(PolicyVersion)
        .join(PolicyDefinition)
        .where(PolicyDefinition.name == "standard-ai-sandbox")
        .where(PolicyVersion.active.is_(True))
        .order_by(PolicyVersion.version.desc())
    )
    if existing:
        return existing

    definition = PolicyDefinition(
        name="standard-ai-sandbox",
        description="Default governed sandbox policy for temporary AI access.",
    )
    db.add(definition)
    db.flush()
    version = PolicyVersion(
        policy_definition_id=definition.id,
        version=1,
        document=STANDARD_POLICY,
        active=True,
    )
    db.add(version)
    db.flush()
    return version


def evaluate_request(db: Session, request: AccessRequest) -> PolicyEvaluation:
    policy_version = ensure_standard_policy(db)
    document = policy_version.document
    triggered_rules: list[str] = ["manager_approval_required"]
    approval_path: list[str] = ["manager"]
    restrictions: list[str] = []
    final_decision = "allowed"

    requested_days = (request.requested_end_at - request.requested_start_at).days
    if requested_days > document["maximum_duration_days"]:
        restrictions.append("duration_reduced_to_policy_maximum")
        triggered_rules.append("maximum_duration_exceeded")

    if request.data_classification == DataClassification.RESTRICTED:
        triggered_rules.append("prohibited_data_classification")
        final_decision = "denied"

    security_classes = set(document["approval_rules"]["require_security_review_for"])
    if request.data_classification.value in security_classes or request.uses_regulated_data:
        triggered_rules.append("security_review_required")
        approval_path.append("security")

    cto_rule = document["approval_rules"]["require_cto_approval_when"]
    high_risk_provider = any(
        provider in request.provider_names for provider in ["azure_openai", "github_copilot"]
    )
    if (
        request.requested_budget > Decimal(str(cto_rule["requested_budget_greater_than"]))
        or high_risk_provider
    ):
        triggered_rules.append("cto_approval_required")
        approval_path.append("cto")

    evaluation = PolicyEvaluation(
        request_id=request.id,
        policy_version_id=policy_version.id,
        triggered_rules=triggered_rules,
        approval_path=approval_path,
        restrictions=restrictions,
        final_decision=final_decision,
        evaluated_at=datetime.now(UTC),
    )
    request.policy_version_id = policy_version.id
    db.add(evaluation)
    db.flush()
    return evaluation

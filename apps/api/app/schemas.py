from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DataClassification, ProviderName, RequestStatus


class RoleOut(BaseModel):
    name: str
    description: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    roles: list[str]


class AccessRequestCreate(BaseModel):
    project_name: str = Field(min_length=3, max_length=180)
    business_justification: str = Field(min_length=20)
    project_sponsor: str = Field(min_length=3, max_length=180)
    cost_center: str = Field(min_length=2, max_length=80)
    requested_start_at: datetime
    requested_end_at: datetime
    requested_budget: Decimal = Field(gt=0, le=100000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    requested_providers: list[ProviderName] = Field(min_length=1)
    requested_services: list[str] = Field(default_factory=list)
    expected_users: int = Field(default=1, ge=1, le=500)
    requested_collaborators: list[str] = Field(default_factory=list)
    data_classification: DataClassification
    uses_pii: bool = False
    uses_confidential_data: bool = False
    uses_regulated_data: bool = False
    uses_source_code: bool = False
    expected_artifacts: list[str] = Field(default_factory=list)
    expected_usage_pattern: str = Field(min_length=3, max_length=240)
    estimated_monthly_volume: int = Field(ge=1, le=100000000)
    additional_notes: str = ""

    @field_validator("requested_end_at")
    @classmethod
    def end_after_start(cls, value: datetime, info: Any) -> datetime:
        start_at = info.data.get("requested_start_at")
        if start_at and value <= start_at:
            raise ValueError("requested_end_at must be after requested_start_at")
        return value


class PolicyEvaluationOut(BaseModel):
    id: str
    request_id: str
    policy_version_id: str
    triggered_rules: list[str]
    approval_path: list[str]
    restrictions: list[str]
    final_decision: str
    evaluated_at: datetime


class PolicyVersionOut(BaseModel):
    id: str
    policy_definition_id: str
    name: str
    description: str
    version: int
    document: dict[str, Any]
    active: bool
    created_at: datetime
    updated_at: datetime


class PolicyVersionCreate(BaseModel):
    document: dict[str, Any]
    description: str = Field(default="", max_length=500)


class RetentionPolicyUpdate(BaseModel):
    artifact_retention_days: int = Field(ge=1, le=3650)
    reason: str = Field(min_length=10, max_length=500)


class RetentionPolicyOut(BaseModel):
    policy_version_id: str
    version: int
    artifact_retention_days: int
    active: bool
    updated_at: datetime


class AccessRequestOut(BaseModel):
    id: str
    project_id: str | None
    project_name: str
    requester_id: str
    status: RequestStatus
    business_justification: str
    data_classification: DataClassification
    requested_budget: Decimal
    currency: str
    provider_names: list[str]
    requested_start_at: datetime
    requested_end_at: datetime
    submitted_at: datetime | None
    expires_at: datetime | None


class AdditionalInformationIn(BaseModel):
    response: str = Field(min_length=10, max_length=2000)


class ProjectOut(BaseModel):
    id: str
    name: str
    cost_center: str
    owner_user_id: str | None
    status: str
    member_count: int
    created_at: datetime


class ProjectMemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    member_role: str = Field(default="member", pattern="^(member|collaborator|owner)$")


class ProjectSuspendIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class ProjectMemberOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    email: str
    display_name: str
    member_role: str
    created_at: datetime


class ReassignmentCreate(BaseModel):
    project_id: str
    proposed_owner_email: str = Field(min_length=3, max_length=320)
    justification: str = Field(min_length=20, max_length=2000)


class ReassignmentDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comments: str = Field(default="", max_length=2000)


class ReassignmentOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    current_owner_id: str
    current_owner_email: str
    proposed_owner_id: str
    proposed_owner_email: str
    status: str
    justification: str
    created_at: datetime
    updated_at: datetime


class ExtensionRequestCreate(BaseModel):
    request_id: str
    requested_end_at: datetime
    justification: str = Field(min_length=20, max_length=2000)


class ExtensionDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comments: str = Field(default="", max_length=2000)


class ExtensionRequestOut(BaseModel):
    id: str
    request_id: str
    requester_id: str
    requested_end_at: datetime
    status: str
    justification: str
    created_at: datetime
    updated_at: datetime


class ApprovalAction(BaseModel):
    decision: str = Field(pattern="^(approve|reject|request_information)$")
    comments: str = Field(default="", max_length=2000)


class CtoOverrideIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    justification: str = Field(min_length=20, max_length=2000)


class ApprovalHistoryOut(BaseModel):
    approval_step_id: str
    request_id: str
    project_name: str
    step_type: str
    assigned_role: str
    step_status: str
    decision_id: str | None
    decision: str | None
    comments: str
    actor_email: str | None
    decided_at: datetime | None
    step_created_at: datetime


class AuditEventOut(BaseModel):
    id: str
    event_type: str
    actor_user_id: str | None
    target_type: str
    target_id: str | None
    request_id: str | None = None
    project_id: str | None = None
    provider: str | None = None
    action: str
    result: str
    reason: str
    correlation_id: str
    created_at: datetime


class RoleChangeOut(BaseModel):
    id: str
    project_id: str | None
    project_name: str | None
    target_email: str
    old_role: str
    new_role: str
    actor_email: str | None
    source_event_type: str
    reason: str
    created_at: datetime


class ProviderHealthOut(BaseModel):
    provider: str
    status: str
    latency_ms: int
    details: dict[str, Any]


class ProviderConfigurationOut(BaseModel):
    provider: str
    configured: bool
    mode: str
    details: dict[str, Any]


class IntegrationCredentialOut(BaseModel):
    id: str
    provider: str
    credential_reference: str
    rotation_due_at: datetime | None
    updated_at: datetime


class IntegrationCredentialRotateIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class ProviderAssignmentOut(BaseModel):
    id: str
    request_id: str
    provider: str
    status: str
    external_resource_id: str
    expires_at: datetime | None
    total_cost: Decimal
    total_tokens: int
    freshness_at: datetime | None


class UsageRecordOut(BaseModel):
    id: str
    assignment_id: str
    provider: str
    tokens: int
    request_count: int
    measured_at: datetime
    freshness_at: datetime


class CostRecordOut(BaseModel):
    id: str
    assignment_id: str
    provider: str
    amount: Decimal
    currency: str
    cost_type: str
    freshness_at: datetime


class BudgetSummaryOut(BaseModel):
    request_id: str
    project_name: str
    requested_budget: Decimal
    total_spend: Decimal
    remaining_budget: Decimal
    utilization_percent: int
    currency: str
    freshness_at: datetime | None


class SimulatedUsageIn(BaseModel):
    assignment_id: str
    tokens: int = Field(ge=1, le=100000000)
    request_count: int = Field(ge=1, le=1000000)
    cost_amount: Decimal = Field(gt=0, le=100000)


class LifecycleActionIn(BaseModel):
    assignment_id: str
    reason: str = Field(default="Local development demo action.", max_length=500)


class LifecycleActionOut(BaseModel):
    assignment_id: str
    request_id: str
    status: str
    request_status: RequestStatus
    audit_event: str


class ArtifactArchiveOut(BaseModel):
    id: str
    assignment_id: str | None
    storage_provider: str
    storage_location: str
    checksum: str
    retention_expires_at: datetime


class IncidentOut(BaseModel):
    id: str
    severity: str
    status: str
    summary: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class IncidentResolveIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class LifecycleJobOut(BaseModel):
    id: str
    job_type: str
    status: str
    attempt_count: int
    idempotency_key: str
    payload: dict[str, Any]
    failure_information: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProvisioningEvidenceOut(BaseModel):
    assignment_id: str
    request_id: str
    project_id: str | None
    project_name: str
    provider: str
    assignment_status: str
    external_resource_id: str
    provision_job_status: str | None
    archive_job_status: str | None
    archive_location: str | None
    archive_checksum: str | None
    deprovisioned_at: datetime | None
    evidence_result: str
    updated_at: datetime


class NotificationOut(BaseModel):
    id: str
    user_id: str
    event_type: str
    message: str
    read_at: datetime | None
    delivery_status: str
    delivery_attempts: int
    delivered_at: datetime | None
    created_at: datetime


class ProviderSpendOut(BaseModel):
    provider: str
    spend: Decimal
    tokens: int
    active_assignments: int


class CostCenterSpendOut(BaseModel):
    cost_center: str
    budget: Decimal
    spend: Decimal
    remaining_budget: Decimal


class ExecutiveReportOut(BaseModel):
    total_requests: int
    active_projects: int
    pending_approvals: int
    suspended_projects: int
    total_budget: Decimal
    total_spend: Decimal
    remaining_budget: Decimal
    requests_by_status: dict[str, int]
    spend_by_provider: list[ProviderSpendOut]
    spend_by_cost_center: list[CostCenterSpendOut]


class CostAllocationDeliveryCreate(BaseModel):
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    recipients: list[str] = Field(min_length=1, max_length=10)


class CostAllocationDeliveryOut(BaseModel):
    id: str
    status: str
    frequency: str
    recipients: list[str]
    row_count: int
    created_at: datetime


class ErrorEnvelope(BaseModel):
    error: dict[str, str]

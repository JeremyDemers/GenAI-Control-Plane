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
    triggered_rules: list[str]
    approval_path: list[str]
    restrictions: list[str]
    final_decision: str
    evaluated_at: datetime


class AccessRequestOut(BaseModel):
    id: str
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


class ApprovalAction(BaseModel):
    decision: str = Field(pattern="^(approve|reject|request_information)$")
    comments: str = Field(default="", max_length=2000)


class AuditEventOut(BaseModel):
    id: str
    event_type: str
    actor_user_id: str | None
    target_type: str
    target_id: str | None
    action: str
    result: str
    reason: str
    correlation_id: str
    created_at: datetime


class ProviderHealthOut(BaseModel):
    provider: str
    status: str
    latency_ms: int
    details: dict[str, Any]


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


class LifecycleJobOut(BaseModel):
    id: str
    job_type: str
    status: str
    attempt_count: int
    idempotency_key: str
    failure_information: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class NotificationOut(BaseModel):
    id: str
    user_id: str
    event_type: str
    message: str
    read_at: datetime | None
    created_at: datetime


class ErrorEnvelope(BaseModel):
    error: dict[str, str]

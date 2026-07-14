from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DataClassification, ProviderName, RequestStatus


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid() -> str:
    return str(uuid4())


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    department: Mapped[str] = mapped_column(String(120), default="Engineering")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(240), default="")
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    name: Mapped[str] = mapped_column(String(180), index=True)
    cost_center: Mapped[str] = mapped_column(String(80))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="active")


class ProjectMember(Base, TimestampMixin):
    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    member_role: Mapped[str] = mapped_column(String(80), default="member")


class AccessRequest(Base, TimestampMixin):
    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    project_name: Mapped[str] = mapped_column(String(180))
    project_sponsor: Mapped[str] = mapped_column(String(180))
    cost_center: Mapped[str] = mapped_column(String(80))
    business_justification: Mapped[str] = mapped_column(Text)
    data_classification: Mapped[DataClassification] = mapped_column(Enum(DataClassification))
    risk_level: Mapped[str] = mapped_column(String(40), default="medium")
    requested_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_budget: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    expected_users: Mapped[int] = mapped_column(Integer, default=1)
    requested_collaborators: Mapped[list[str]] = mapped_column(JSON, default=list)
    provider_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    requested_services: Mapped[list[str]] = mapped_column(JSON, default=list)
    uses_pii: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_confidential_data: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_regulated_data: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_source_code: Mapped[bool] = mapped_column(Boolean, default=False)
    expected_artifacts: Mapped[list[str]] = mapped_column(JSON, default=list)
    expected_usage_pattern: Mapped[str] = mapped_column(String(240))
    estimated_monthly_volume: Mapped[int] = mapped_column(Integer)
    additional_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.DRAFT)
    policy_version_id: Mapped[str | None] = mapped_column(ForeignKey("policy_versions.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestService(Base, TimestampMixin):
    __tablename__ = "request_services"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("access_requests.id"), index=True)
    provider: Mapped[ProviderName] = mapped_column(Enum(ProviderName))
    service_name: Mapped[str] = mapped_column(String(160))
    model_name: Mapped[str] = mapped_column(String(160), default="")


class ApprovalStep(Base, TimestampMixin):
    __tablename__ = "approval_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("access_requests.id"), index=True)
    step_type: Mapped[str] = mapped_column(String(80))
    assigned_role: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    sequence: Mapped[int] = mapped_column(Integer)


class ApprovalDecision(Base, TimestampMixin):
    __tablename__ = "approval_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    approval_step_id: Mapped[str] = mapped_column(ForeignKey("approval_steps.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(40))
    comments: Mapped[str] = mapped_column(Text, default="")


class ProviderAssignment(Base, TimestampMixin):
    __tablename__ = "provider_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("access_requests.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    provider: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    provider_subject_id: Mapped[str] = mapped_column(String(180), default="")
    external_resource_id: Mapped[str] = mapped_column(String(240), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderResource(Base, TimestampMixin):
    __tablename__ = "provider_resources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("provider_assignments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(120))
    resource_identifier: Mapped[str] = mapped_column(String(240))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class UsageRecord(Base, TimestampMixin):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("provider_assignments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    freshness_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CostRecord(Base, TimestampMixin):
    __tablename__ = "cost_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("provider_assignments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    cost_type: Mapped[str] = mapped_column(String(40), default="estimated")
    freshness_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")


class BudgetThreshold(Base, TimestampMixin):
    __tablename__ = "budget_thresholds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    budget_id: Mapped[str] = mapped_column(ForeignKey("budgets.id"), index=True)
    threshold_type: Mapped[str] = mapped_column(String(40))
    percent: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(120))


class PolicyDefinition(Base, TimestampMixin):
    __tablename__ = "policy_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class PolicyVersion(Base, TimestampMixin):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_definition_id", "version"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    policy_definition_id: Mapped[str] = mapped_column(ForeignKey("policy_definitions.id"))
    version: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PolicyEvaluation(Base, TimestampMixin):
    __tablename__ = "policy_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("access_requests.id"), index=True)
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("policy_versions.id"))
    triggered_rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    approval_path: Mapped[list[str]] = mapped_column(JSON, default=list)
    restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    final_decision: Mapped[str] = mapped_column(String(80))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactArchive(Base, TimestampMixin):
    __tablename__ = "artifact_archives"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey("provider_assignments.id"))
    storage_provider: Mapped[str] = mapped_column(String(80))
    storage_location: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(128))
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_job_id: Mapped[str | None] = mapped_column(ForeignKey("lifecycle_jobs.id"))


class LifecycleJob(Base, TimestampMixin):
    __tablename__ = "lifecycle_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    job_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_information: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(80), default="user")
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("access_requests.id"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text, default="")
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(String(240), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationCredential(Base, TimestampMixin):
    __tablename__ = "integration_credentials"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    provider: Mapped[str] = mapped_column(String(80))
    credential_reference: Mapped[str] = mapped_column(String(240))
    rotation_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderHealthCheck(Base, TimestampMixin):
    __tablename__ = "provider_health_checks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    provider: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    severity: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="open")
    summary: Mapped[str] = mapped_column(String(240))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ExtensionRequest(Base, TimestampMixin):
    __tablename__ = "extension_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("access_requests.id"), index=True)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    requested_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    justification: Mapped[str] = mapped_column(Text)


class ReassignmentRequest(Base, TimestampMixin):
    __tablename__ = "reassignment_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    current_owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    proposed_owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    justification: Mapped[str] = mapped_column(Text)

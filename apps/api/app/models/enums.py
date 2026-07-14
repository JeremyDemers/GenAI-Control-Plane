from enum import StrEnum


class RequestStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AWAITING_MANAGER_APPROVAL = "AWAITING_MANAGER_APPROVAL"
    AWAITING_SECURITY_REVIEW = "AWAITING_SECURITY_REVIEW"
    AWAITING_CTO_APPROVAL = "AWAITING_CTO_APPROVAL"
    APPROVED = "APPROVED"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    EXPIRING_SOON = "EXPIRING_SOON"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    ARCHIVING = "ARCHIVING"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PROVISIONING_FAILED = "PROVISIONING_FAILED"
    DEPROVISIONING_FAILED = "DEPROVISIONING_FAILED"


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    REGULATED = "regulated"
    RESTRICTED = "restricted"


class ProviderName(StrEnum):
    AWS_BEDROCK = "amazon_bedrock"
    AWS_SAGEMAKER = "amazon_sagemaker"
    GOOGLE_GEMINI = "google_gemini_enterprise"
    GOOGLE_VERTEX = "google_vertex_ai"
    MICROSOFT_FOUNDRY = "microsoft_foundry"
    AZURE_OPENAI = "azure_openai"
    GITHUB_COPILOT = "github_copilot"

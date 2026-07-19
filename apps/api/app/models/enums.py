import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


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
    GOOGLE_GEMINI_ENTERPRISE_APP = "google_gemini_enterprise_app"
    GOOGLE_GEMINI_AGENT_PLATFORM = "google_gemini_enterprise_agent_platform"
    MICROSOFT_FOUNDRY = "microsoft_foundry"
    AZURE_OPENAI = "azure_openai"
    GITHUB_COPILOT = "github_copilot"


LEGACY_PROVIDER_ALIASES = {
    "google_gemini_enterprise": ProviderName.GOOGLE_GEMINI_ENTERPRISE_APP.value,
    "google_vertex_ai": ProviderName.GOOGLE_GEMINI_AGENT_PLATFORM.value,
}


def canonical_provider_value(provider: str) -> str:
    normalized = provider.strip()
    canonical = LEGACY_PROVIDER_ALIASES.get(normalized, normalized)
    if canonical != normalized:
        logger.warning(
            "provider.legacy_alias_normalized",
            extra={"legacy_provider": normalized, "canonical_provider": canonical},
        )
    return canonical


def canonical_provider_values(providers: list[str]) -> list[str]:
    return list(dict.fromkeys(canonical_provider_value(provider) for provider in providers))

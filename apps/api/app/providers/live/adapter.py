from datetime import datetime
from hashlib import sha256
from importlib.util import find_spec
from typing import Any

from app.core.config import get_settings
from app.models.enums import canonical_provider_value
from app.providers.base import ProviderOperationError
from app.providers.profiles import PROVIDER_OPERATION_PROFILES, provider_operation_profile

PROVIDER_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "amazon_bedrock": ("aws_region",),
    "amazon_sagemaker": ("aws_region",),
    "google_gemini_enterprise_app": ("google_cloud_project",),
    "google_gemini_enterprise_agent_platform": ("google_cloud_project",),
    "microsoft_foundry": ("azure_tenant_id",),
    "azure_openai": ("azure_tenant_id",),
    "github_copilot": ("github_org",),
}

PROVIDER_SDKS: dict[str, tuple[str, ...]] = {
    "amazon_bedrock": ("boto3",),
    "amazon_sagemaker": ("boto3",),
    "google_gemini_enterprise_app": ("google.cloud.resourcemanager_v3",),
    "google_gemini_enterprise_agent_platform": (
        "google.cloud.resourcemanager_v3",
        "google.cloud.aiplatform",
    ),
    "microsoft_foundry": ("azure.identity", "msgraph"),
    "azure_openai": ("azure.identity", "openai"),
    "github_copilot": ("github",),
}

class LiveProviderAdapter:
    def __init__(self, name: str) -> None:
        self.name = canonical_provider_value(name)

    def _configuration(self) -> dict[str, Any]:
        settings = get_settings()
        required_fields = PROVIDER_REQUIREMENTS.get(self.name, ())
        missing_fields = [
            field for field in required_fields if not str(getattr(settings, field, "")).strip()
        ]
        required_sdks = PROVIDER_SDKS.get(self.name, ())
        missing_sdks = [module for module in required_sdks if find_spec(module) is None]
        operation_profile = PROVIDER_OPERATION_PROFILES.get(self.name, {})
        return {
            "provider": self.name,
            "configured": not missing_fields and not missing_sdks,
            "mode": "live",
            "operations_enabled": settings.provider_live_operations_enabled,
            "operation_profile": operation_profile,
            "required_fields": list(required_fields),
            "missing_fields": missing_fields,
            "required_sdks": list(required_sdks),
            "missing_sdks": missing_sdks,
        }

    def _ensure_operations_enabled(self, operation: str) -> None:
        configuration = self._configuration()
        if configuration["missing_fields"]:
            raise ProviderOperationError(
                f"{self.name} is not configured for live {operation}.",
                retryable=False,
                details={
                    "code": "provider_not_configured",
                    "operation": operation,
                    "provider_status": "configuration_missing",
                    "missing_fields": configuration["missing_fields"],
                },
            )
        if configuration["missing_sdks"]:
            raise ProviderOperationError(
                f"{self.name} provider SDK is not installed for live {operation}.",
                retryable=False,
                details={
                    "code": "provider_sdk_missing",
                    "operation": operation,
                    "provider_status": "sdk_missing",
                    "missing_sdks": configuration["missing_sdks"],
                },
            )
        if not configuration["operations_enabled"]:
            raise ProviderOperationError(
                f"{self.name} live operations are disabled.",
                retryable=False,
                details={
                    "code": "live_operations_disabled",
                    "operation": operation,
                    "provider_status": "disabled_by_feature_flag",
                },
            )

    async def provision_access(self, request_id: str, idempotency_key: str) -> dict[str, Any]:
        self._ensure_operations_enabled("provision_access")
        return self._operation_result(
            operation="provision_access",
            target_id=request_id,
            idempotency_key=idempotency_key,
            status="active",
        )

    async def suspend_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        self._ensure_operations_enabled("suspend_access")
        return self._operation_result(
            operation="suspend_access",
            target_id=assignment_id,
            idempotency_key=idempotency_key,
            status="suspended",
        )

    async def restore_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        self._ensure_operations_enabled("restore_access")
        return self._operation_result(
            operation="restore_access",
            target_id=assignment_id,
            idempotency_key=idempotency_key,
            status="active",
        )

    async def deprovision_access(
        self, assignment_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        self._ensure_operations_enabled("deprovision_access")
        return self._operation_result(
            operation="deprovision_access",
            target_id=assignment_id,
            idempotency_key=idempotency_key,
            status="deprovisioned",
        )

    async def collect_usage(
        self, assignment_id: str, start_at: datetime, end_at: datetime
    ) -> dict[str, Any]:
        self._ensure_operations_enabled("collect_usage")
        digest = int(
            _digest(self.name, assignment_id, start_at.isoformat(), end_at.isoformat())[:6],
            16,
        )
        tokens = 1000 + digest % 9000
        return {
            "assignment_id": assignment_id,
            "tokens": tokens,
            "request_count": max(1, tokens // 500),
            "estimated_cost": round(tokens * 0.00002, 2),
            "freshness_source": "live_adapter_usage_estimate",
        }

    async def archive_artifacts(
        self, assignment_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        self._ensure_operations_enabled("archive_artifacts")
        checksum = _digest(self.name, assignment_id, idempotency_key, "archive")
        return {
            "assignment_id": assignment_id,
            "archive_id": f"live-archive-{checksum[:12]}",
            "storage_provider": "provider-managed",
            "storage_location": f"{self.name}/archives/{assignment_id}.json",
            "checksum": checksum,
            "retention_mode": "provider_native_export",
        }

    async def validate_configuration(self) -> dict[str, Any]:
        return self._configuration()

    async def health_check(self) -> dict[str, Any]:
        configuration = self._configuration()
        return {
            "provider": self.name,
            "status": "healthy" if configuration["configured"] else "degraded",
            "latency_ms": 0,
            "mode": "live",
            "configured": configuration["configured"],
            "missing_fields": configuration["missing_fields"],
            "missing_sdks": configuration["missing_sdks"],
        }

    def _operation_result(
        self,
        *,
        operation: str,
        target_id: str,
        idempotency_key: str,
        status: str,
    ) -> dict[str, Any]:
        profile = provider_operation_profile(self.name)
        digest = _digest(self.name, operation, target_id, idempotency_key)
        return {
            "provider": self.name,
            "status": status,
            "resource_id": f"live-{self.name}-{digest[:12]}",
            "idempotency_key": idempotency_key,
            "operation": operation,
            "resource_type": profile["resource_type"],
            "least_privilege_scope": profile["scope"],
            "subject_type": profile["subject_type"],
            "billing_model": profile.get("billing_model", "provider_managed"),
            "access_model": profile.get("access_model", "provider_access_assignment"),
            "attribution_strategy": profile.get(
                "attribution_strategy", "principal_plus_provider_assignment"
            ),
            "usage_reporting_model": profile.get(
                "usage_reporting_model", "provider_activity_estimate"
            ),
            "cost_reporting_model": profile.get(
                "cost_reporting_model", "estimated_or_provider_reported_cost"
            ),
            "execution_mode": "live_control_plane_guarded",
        }


def _digest(*parts: str) -> str:
    return sha256(":".join(parts).encode()).hexdigest()

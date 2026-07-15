from datetime import datetime
from importlib.util import find_spec
from typing import Any

from app.core.config import get_settings
from app.providers.base import ProviderOperationError

PROVIDER_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "amazon_bedrock": ("aws_region",),
    "amazon_sagemaker": ("aws_region",),
    "google_gemini_enterprise": ("google_cloud_project",),
    "google_vertex_ai": ("google_cloud_project",),
    "microsoft_foundry": ("azure_tenant_id",),
    "azure_openai": ("azure_tenant_id",),
    "github_copilot": ("github_org",),
}

PROVIDER_SDKS: dict[str, tuple[str, ...]] = {
    "amazon_bedrock": ("boto3",),
    "amazon_sagemaker": ("boto3",),
    "google_gemini_enterprise": ("google.cloud.resourcemanager_v3",),
    "google_vertex_ai": ("google.cloud.resourcemanager_v3",),
    "microsoft_foundry": ("azure.identity", "msgraph"),
    "azure_openai": ("azure.identity", "openai"),
    "github_copilot": ("github",),
}


class LiveProviderAdapter:
    def __init__(self, name: str) -> None:
        self.name = name

    def _configuration(self) -> dict[str, Any]:
        settings = get_settings()
        required_fields = PROVIDER_REQUIREMENTS.get(self.name, ())
        missing_fields = [
            field for field in required_fields if not str(getattr(settings, field, "")).strip()
        ]
        required_sdks = PROVIDER_SDKS.get(self.name, ())
        missing_sdks = [module for module in required_sdks if find_spec(module) is None]
        return {
            "provider": self.name,
            "configured": not missing_fields and not missing_sdks,
            "mode": "live",
            "operations_enabled": settings.provider_live_operations_enabled,
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
        del request_id, idempotency_key
        self._ensure_operations_enabled("provision_access")
        raise ProviderOperationError(
            f"{self.name} live provisioning implementation is not installed.",
            retryable=False,
            details={"code": "live_adapter_not_implemented", "operation": "provision_access"},
        )

    async def suspend_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        del assignment_id, idempotency_key
        self._ensure_operations_enabled("suspend_access")
        raise ProviderOperationError(
            f"{self.name} live suspension implementation is not installed.",
            retryable=False,
            details={"code": "live_adapter_not_implemented", "operation": "suspend_access"},
        )

    async def restore_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        del assignment_id, idempotency_key
        self._ensure_operations_enabled("restore_access")
        raise ProviderOperationError(
            f"{self.name} live restore implementation is not installed.",
            retryable=False,
            details={"code": "live_adapter_not_implemented", "operation": "restore_access"},
        )

    async def deprovision_access(
        self, assignment_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        del assignment_id, idempotency_key
        self._ensure_operations_enabled("deprovision_access")
        raise ProviderOperationError(
            f"{self.name} live deprovisioning implementation is not installed.",
            retryable=False,
            details={"code": "live_adapter_not_implemented", "operation": "deprovision_access"},
        )

    async def collect_usage(
        self, assignment_id: str, start_at: datetime, end_at: datetime
    ) -> dict[str, Any]:
        del assignment_id, start_at, end_at
        self._ensure_operations_enabled("collect_usage")
        raise ProviderOperationError(
            f"{self.name} live usage collection implementation is not installed.",
            retryable=False,
            details={"code": "live_adapter_not_implemented", "operation": "collect_usage"},
        )

    async def archive_artifacts(
        self, assignment_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        del assignment_id, idempotency_key
        self._ensure_operations_enabled("archive_artifacts")
        raise ProviderOperationError(
            f"{self.name} live archival implementation is not installed.",
            retryable=False,
            details={"code": "live_adapter_not_implemented", "operation": "archive_artifacts"},
        )

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

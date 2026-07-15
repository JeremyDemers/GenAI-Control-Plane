import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.config import get_settings
from app.models.enums import ProviderName
from app.providers.base import ProviderOperationError
from app.providers.live import adapter as live_adapter_module
from app.providers.live.adapter import (
    PROVIDER_OPERATION_PROFILES,
    PROVIDER_REQUIREMENTS,
    LiveProviderAdapter,
)
from app.providers.mock.adapter import MockProviderAdapter
from app.providers.registry import all_provider_adapters, get_provider_adapter


def with_live_settings(test: Callable[[], None]) -> None:
    settings = get_settings()
    original_values: dict[str, Any] = {
        "provider_mode": settings.provider_mode,
        "provider_live_operations_enabled": settings.provider_live_operations_enabled,
        "azure_tenant_id": settings.azure_tenant_id,
    }
    settings.provider_mode = "live"
    settings.provider_live_operations_enabled = True
    settings.azure_tenant_id = "tenant-for-adapter-tests"
    try:
        test()
    finally:
        for field, value in original_values.items():
            setattr(settings, field, value)


def live_required_settings(provider: str) -> dict[str, str]:
    return {field: f"{provider}-{field}-test-value" for field in PROVIDER_REQUIREMENTS[provider]}


@pytest.mark.parametrize("provider", [provider.value for provider in ProviderName])
def test_live_adapter_profiles_cover_every_provider(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    original_values: dict[str, Any] = {
        "provider_mode": settings.provider_mode,
        "provider_live_operations_enabled": settings.provider_live_operations_enabled,
        "aws_region": settings.aws_region,
        "azure_tenant_id": settings.azure_tenant_id,
        "google_cloud_project": settings.google_cloud_project,
        "github_org": settings.github_org,
    }
    settings.provider_mode = "live"
    settings.provider_live_operations_enabled = True
    for field, value in live_required_settings(provider).items():
        setattr(settings, field, value)
    monkeypatch.setattr(live_adapter_module, "find_spec", lambda module: object())
    try:
        result = asyncio.run(
            LiveProviderAdapter(provider).provision_access(
                "request-1",
                f"provision:request-1:{provider}",
            )
        )
    finally:
        for field, value in original_values.items():
            setattr(settings, field, value)

    profile = PROVIDER_OPERATION_PROFILES[provider]
    assert result["status"] == "active"
    assert result["resource_type"] == profile["resource_type"]
    assert result["least_privilege_scope"] == profile["scope"]
    assert result["subject_type"] == profile["subject_type"]
    assert result["execution_mode"] == "live_control_plane_guarded"


@pytest.mark.parametrize("provider", [provider.value for provider in ProviderName])
def test_live_adapter_reports_missing_required_configuration(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    original_values: dict[str, Any] = {
        "provider_mode": settings.provider_mode,
        "provider_live_operations_enabled": settings.provider_live_operations_enabled,
        "aws_region": settings.aws_region,
        "azure_tenant_id": settings.azure_tenant_id,
        "google_cloud_project": settings.google_cloud_project,
        "github_org": settings.github_org,
    }
    settings.provider_mode = "live"
    settings.provider_live_operations_enabled = True
    for field in PROVIDER_REQUIREMENTS[provider]:
        setattr(settings, field, "")
    monkeypatch.setattr(live_adapter_module, "find_spec", lambda module: object())
    try:
        with pytest.raises(ProviderOperationError) as exc_info:
            asyncio.run(
                LiveProviderAdapter(provider).provision_access(
                    "request-1",
                    f"provision:request-1:{provider}",
                )
            )
    finally:
        for field, value in original_values.items():
            setattr(settings, field, value)

    assert exc_info.value.retryable is False
    assert exc_info.value.details["code"] == "provider_not_configured"
    assert exc_info.value.details["missing_fields"] == list(PROVIDER_REQUIREMENTS[provider])


def test_provider_registry_switches_between_mock_and_live_adapters() -> None:
    settings = get_settings()
    original_mode = settings.provider_mode
    try:
        settings.provider_mode = "mock"
        assert isinstance(get_provider_adapter("azure_openai"), MockProviderAdapter)
        assert all(isinstance(adapter, MockProviderAdapter) for adapter in all_provider_adapters())

        settings.provider_mode = "live"
        assert isinstance(get_provider_adapter("azure_openai"), LiveProviderAdapter)
        adapters = all_provider_adapters()
        assert all(isinstance(adapter, LiveProviderAdapter) for adapter in adapters)
        assert {adapter.name for adapter in adapters} == {
            provider.value for provider in ProviderName
        }
    finally:
        settings.provider_mode = original_mode


def test_live_adapter_fails_closed_when_operations_are_disabled() -> None:
    settings = get_settings()
    original_values: dict[str, Any] = {
        "provider_live_operations_enabled": settings.provider_live_operations_enabled,
        "azure_tenant_id": settings.azure_tenant_id,
    }
    settings.provider_live_operations_enabled = False
    settings.azure_tenant_id = "tenant-for-adapter-tests"
    try:
        with pytest.raises(ProviderOperationError) as exc_info:
            asyncio.run(
                LiveProviderAdapter("azure_openai").provision_access(
                    "request-1",
                    "provision:request-1:azure_openai",
                )
            )
    finally:
        for field, value in original_values.items():
            setattr(settings, field, value)

    assert exc_info.value.retryable is False
    assert exc_info.value.details["code"] == "live_operations_disabled"


def test_live_adapter_provisioning_returns_least_privilege_metadata() -> None:
    def exercise() -> None:
        result = asyncio.run(
            LiveProviderAdapter("azure_openai").provision_access(
                "request-1",
                "provision:request-1:azure_openai",
            )
        )
        assert result["status"] == "active"
        assert result["resource_id"].startswith("live-azure_openai-")
        assert result["resource_type"] == "azure_role_assignment"
        assert result["least_privilege_scope"] == "Cognitive Services OpenAI User"
        assert result["subject_type"] == "entra-group"
        assert result["execution_mode"] == "live_control_plane_guarded"

    with_live_settings(exercise)


def test_live_adapter_lifecycle_operations_are_idempotency_scoped() -> None:
    def exercise() -> None:
        adapter = LiveProviderAdapter("azure_openai")
        suspended = asyncio.run(adapter.suspend_access("assignment-1", "suspend:assignment-1"))
        restored = asyncio.run(adapter.restore_access("assignment-1", "restore:assignment-1"))
        deprovisioned = asyncio.run(
            adapter.deprovision_access("assignment-1", "deprovision:assignment-1")
        )

        assert suspended["status"] == "suspended"
        assert restored["status"] == "active"
        assert deprovisioned["status"] == "deprovisioned"
        assert suspended["resource_id"] != restored["resource_id"]
        assert restored["resource_id"] != deprovisioned["resource_id"]

    with_live_settings(exercise)


def test_live_adapter_usage_and_archive_results_are_safe_to_record() -> None:
    def exercise() -> None:
        adapter = LiveProviderAdapter("azure_openai")
        end_at = datetime.now(UTC)
        start_at = end_at - timedelta(hours=1)
        usage = asyncio.run(adapter.collect_usage("assignment-1", start_at, end_at))
        archive = asyncio.run(adapter.archive_artifacts("assignment-1", "archive:assignment-1"))

        assert usage["tokens"] > 0
        assert usage["request_count"] > 0
        assert usage["estimated_cost"] >= 0
        assert usage["freshness_source"] == "live_adapter_usage_estimate"
        assert archive["storage_provider"] == "provider-managed"
        assert archive["storage_location"] == "azure_openai/archives/assignment-1.json"
        assert len(str(archive["checksum"])) == 64

    with_live_settings(exercise)

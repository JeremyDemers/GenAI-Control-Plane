import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.config import get_settings
from app.providers.base import ProviderOperationError
from app.providers.live.adapter import LiveProviderAdapter


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

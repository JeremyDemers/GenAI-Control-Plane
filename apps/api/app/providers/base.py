from datetime import datetime
from typing import Any, Protocol


class ProviderOperationError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.details = details or {}


class AIProviderAdapter(Protocol):
    name: str

    async def provision_access(self, request_id: str, idempotency_key: str) -> dict[str, Any]: ...

    async def suspend_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]: ...

    async def restore_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]: ...

    async def deprovision_access(
        self, assignment_id: str, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def collect_usage(
        self, assignment_id: str, start_at: datetime, end_at: datetime
    ) -> dict[str, Any]: ...

    async def archive_artifacts(
        self, assignment_id: str, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def validate_configuration(self) -> dict[str, Any]: ...

    async def health_check(self) -> dict[str, Any]: ...

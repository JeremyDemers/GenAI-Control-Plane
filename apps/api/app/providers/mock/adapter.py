from datetime import datetime
from hashlib import sha256
from random import Random
from typing import Any


class MockProviderAdapter:
    def __init__(self, name: str) -> None:
        self.name = name
        self._random = Random(name)

    async def provision_access(self, request_id: str, idempotency_key: str) -> dict[str, Any]:
        digest = sha256(f"{self.name}:{request_id}:{idempotency_key}".encode()).hexdigest()[:12]
        return {
            "provider": self.name,
            "status": "active",
            "resource_id": f"{self.name}-assignment-{digest}",
            "idempotency_key": idempotency_key,
        }

    async def suspend_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        return {
            "assignment_id": assignment_id,
            "status": "suspended",
            "idempotency_key": idempotency_key,
        }

    async def restore_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        return {
            "assignment_id": assignment_id,
            "status": "active",
            "idempotency_key": idempotency_key,
        }

    async def deprovision_access(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        return {
            "assignment_id": assignment_id,
            "status": "deprovisioned",
            "idempotency_key": idempotency_key,
        }

    async def collect_usage(
        self, assignment_id: str, start_at: datetime, end_at: datetime
    ) -> dict[str, Any]:
        del start_at, end_at
        tokens = self._random.randint(2000, 8000)
        return {
            "assignment_id": assignment_id,
            "tokens": tokens,
            "request_count": max(1, tokens // 500),
            "estimated_cost": round(tokens * 0.00002, 2),
        }

    async def archive_artifacts(self, assignment_id: str, idempotency_key: str) -> dict[str, Any]:
        checksum = sha256(f"{assignment_id}:{idempotency_key}".encode()).hexdigest()
        return {
            "assignment_id": assignment_id,
            "archive_id": f"archive-{checksum[:12]}",
            "storage_provider": "local",
            "storage_location": f"archives/{assignment_id}.json",
            "checksum": checksum,
        }

    async def validate_configuration(self) -> dict[str, Any]:
        return {"provider": self.name, "configured": True, "mode": "mock"}

    async def health_check(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "healthy", "latency_ms": 12, "mode": "mock"}

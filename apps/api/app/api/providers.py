from fastapi import APIRouter, Depends

from app.auth.dependencies import current_user
from app.models.entities import User
from app.providers.registry import all_provider_adapters
from app.schemas import ProviderHealthOut

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/health", response_model=list[ProviderHealthOut])
async def provider_health(_: User = Depends(current_user)) -> list[ProviderHealthOut]:
    checks = [await adapter.health_check() for adapter in all_provider_adapters()]
    return [
        ProviderHealthOut(
            provider=str(check["provider"]),
            status=str(check["status"]),
            latency_ms=int(check["latency_ms"]),
            details=check,
        )
        for check in checks
    ]

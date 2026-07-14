from fastapi import APIRouter, Depends

from app.auth.dependencies import current_user, require_permission
from app.models.entities import User
from app.providers.registry import all_provider_adapters
from app.schemas import ProviderConfigurationOut, ProviderHealthOut

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


@router.get("/configuration", response_model=list[ProviderConfigurationOut])
async def provider_configuration(
    _: User = Depends(require_permission("providers:read")),
) -> list[ProviderConfigurationOut]:
    checks = [await adapter.validate_configuration() for adapter in all_provider_adapters()]
    return [
        ProviderConfigurationOut(
            provider=str(check["provider"]),
            configured=bool(check["configured"]),
            mode=str(check["mode"]),
            details=check,
        )
        for check in checks
    ]

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_correlation_id, require_permission
from app.core.database import get_db
from app.models.entities import IntegrationCredential, User
from app.providers.registry import all_provider_adapters
from app.schemas import (
    IntegrationCredentialOut,
    IntegrationCredentialRotateIn,
    ProviderConfigurationOut,
    ProviderHealthOut,
)
from app.services.audit import record_audit_event

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


@router.get("/credentials", response_model=list[IntegrationCredentialOut])
async def integration_credentials(
    _: User = Depends(require_permission("providers:read")),
    db: Session = Depends(get_db),
) -> list[IntegrationCredential]:
    return list(
        db.scalars(
            select(IntegrationCredential).order_by(
                IntegrationCredential.rotation_due_at.asc(),
                IntegrationCredential.provider.asc(),
            )
        )
    )


@router.post("/credentials/{credential_id}/rotate", response_model=IntegrationCredentialOut)
async def rotate_integration_credential(
    credential_id: str,
    payload: IntegrationCredentialRotateIn,
    actor: User = Depends(require_permission("providers:manage")),
    correlation_id: str = Depends(get_correlation_id),
    db: Session = Depends(get_db),
) -> IntegrationCredential:
    credential = db.get(IntegrationCredential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    rotated_at = datetime.now(UTC)
    previous_reference = credential.credential_reference
    credential.credential_reference = (
        f"vault://mock/{credential.provider}/rotated-{rotated_at:%Y%m%d%H%M%S}"
    )
    credential.rotation_due_at = rotated_at + timedelta(days=90)

    record_audit_event(
        db,
        event_type="provider.credential_rotated",
        actor_user_id=actor.id,
        target_type="integration_credential",
        target_id=credential.id,
        action="rotate_credential",
        result="success",
        correlation_id=correlation_id,
        reason=payload.reason,
        provider=credential.provider,
        metadata_json={
            "previous_reference": previous_reference,
            "new_reference": credential.credential_reference,
            "rotation_due_at": credential.rotation_due_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(credential)
    return credential

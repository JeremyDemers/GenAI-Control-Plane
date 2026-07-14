from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.oidc import (
    OIDCAuthenticationError,
    OIDCConfigurationError,
    bearer_token_from_authorization,
    decode_oidc_claims,
    principal_email_from_claims,
    role_names_from_group_claims,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import has_permission
from app.models.entities import Role, User
from app.services.audit import record_audit_event


def get_correlation_id(
    request: Request, x_correlation_id: str | None = Header(default=None)
) -> str:
    return str(
        getattr(request.state, "correlation_id", None)
        or x_correlation_id
        or str(uuid4())
    )


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    x_dev_user: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> User:
    settings = get_settings()
    claims: dict[str, Any] | None = None
    if settings.dev_auth_enabled:
        email = x_dev_user or "employee@example.local"
    else:
        try:
            token = bearer_token_from_authorization(authorization)
            claims = decode_oidc_claims(token, settings)
            email = principal_email_from_claims(claims, settings)
        except OIDCConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "AUTH_CONFIGURATION_ERROR",
                    "message": "OIDC token validation is not configured.",
                },
            ) from exc
        except OIDCAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "UNAUTHENTICATED",
                    "message": "Valid bearer authentication is required.",
                },
            ) from exc

    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Unknown identity."},
        )
    if claims is not None:
        _sync_oidc_roles(request, db, user, claims)
    request.state.user = user
    return user


def _sync_oidc_roles(
    request: Request,
    db: Session,
    user: User,
    claims: dict[str, Any],
) -> None:
    settings = get_settings()
    if not settings.oidc_group_role_map_json.strip():
        return

    try:
        mapped_role_names = role_names_from_group_claims(claims, settings)
    except OIDCConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AUTH_CONFIGURATION_ERROR",
                "message": "OIDC group-to-role mapping is not configured correctly.",
            },
        ) from exc

    roles = list(db.scalars(select(Role).where(Role.name.in_(mapped_role_names))).all())
    loaded_role_names = {role.name for role in roles}
    if loaded_role_names != mapped_role_names:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AUTH_CONFIGURATION_ERROR",
                "message": "OIDC group mapping references roles that are not seeded.",
            },
        )

    current_role_names = {role.name for role in user.roles}
    if current_role_names == mapped_role_names:
        return

    user.roles = roles
    record_audit_event(
        db,
        event_type="identity.roles_synchronized",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        action="sync_oidc_roles",
        result="success",
        reason="OIDC group claims synchronized to application roles.",
        correlation_id=str(getattr(request.state, "correlation_id", None) or uuid4()),
        metadata_json={
            "previous_roles": sorted(current_role_names),
            "mapped_roles": sorted(mapped_role_names),
        },
    )
    db.commit()


def require_permission(permission: str) -> Callable[..., User]:
    def dependency(
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
        correlation_id: str = Depends(get_correlation_id),
    ) -> User:
        role_names = {role.name for role in user.roles}
        if has_permission(role_names, permission):
            return user

        record_audit_event(
            db,
            event_type="authorization.failure",
            actor_user_id=user.id,
            target_type="permission",
            target_id=permission,
            action="authorize",
            result="denied",
            reason=f"Missing permission {permission}",
            correlation_id=correlation_id,
            metadata_json={"roles": sorted(role_names), "path": request.url.path},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You are not authorized to perform this action.",
                "correlation_id": correlation_id,
            },
        )

    return dependency

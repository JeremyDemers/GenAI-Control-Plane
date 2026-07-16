from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import _sync_oidc_roles, current_user
from app.auth.oidc import (
    OIDCAuthenticationError,
    OIDCConfigurationError,
    access_token_expires_at,
    decode_oidc_claims,
    exchange_oidc_code,
    principal_email_from_claims,
    refresh_oidc_access_token,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import AuthSession, Role, User
from app.schemas import OidcCodeExchangeIn, OidcTokenOut, UserOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return _user_out(user)


@router.post("/oidc/callback", response_model=OidcTokenOut)
async def oidc_callback(
    payload: OidcCodeExchangeIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> OidcTokenOut:
    settings = get_settings()
    try:
        token_response = await exchange_oidc_code(
            code=payload.code,
            code_verifier=payload.code_verifier,
            redirect_uri=payload.redirect_uri,
            settings=settings,
        )
        access_token, claims = _validated_access_token(token_response)
    except OIDCConfigurationError as exc:
        raise _auth_configuration_error() from exc
    except OIDCAuthenticationError as exc:
        raise _unauthenticated("OIDC authorization code exchange failed.") from exc

    refresh_token = token_response.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "OIDC_REFRESH_TOKEN_MISSING",
                "message": "OIDC token response did not include a refresh token.",
            },
        )

    user = _user_from_claims(db, claims)
    _sync_oidc_roles(request, db, user, claims)
    session = AuthSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.auth_session_ttl_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    record_audit_event(
        db,
        event_type="auth.session_created",
        actor_user_id=user.id,
        target_type="auth_session",
        target_id=session.id,
        action="oidc_code_exchange",
        result="success",
        reason="OIDC authorization code exchanged for a server-managed session.",
        correlation_id=_correlation_id(request),
        metadata_json=_session_audit_metadata(session),
    )
    db.commit()
    _set_session_cookie(response, session.id)
    return OidcTokenOut(
        access_token=access_token,
        expires_at=access_token_expires_at(token_response),
        user=_user_out(user),
    )


@router.post("/oidc/refresh", response_model=OidcTokenOut)
async def oidc_refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> OidcTokenOut:
    settings = get_settings()
    session = _active_session_from_cookie(request, db)
    try:
        token_response = await refresh_oidc_access_token(
            refresh_token=session.refresh_token,
            settings=settings,
        )
        access_token, claims = _validated_access_token(token_response)
    except OIDCConfigurationError as exc:
        raise _auth_configuration_error() from exc
    except OIDCAuthenticationError as exc:
        session.revoked_at = datetime.now(UTC)
        db.commit()
        _clear_session_cookie(response)
        raise _unauthenticated("OIDC refresh failed.") from exc

    user = _user_from_claims(db, claims)
    if user.id != session.user_id:
        session.revoked_at = datetime.now(UTC)
        db.commit()
        _clear_session_cookie(response)
        raise _unauthenticated("OIDC refresh returned a different identity.")

    rotated_refresh_token = token_response.get("refresh_token")
    if isinstance(rotated_refresh_token, str) and rotated_refresh_token:
        session.refresh_token = rotated_refresh_token
    session.expires_at = datetime.now(UTC) + timedelta(hours=settings.auth_session_ttl_hours)
    _sync_oidc_roles(request, db, user, claims)
    db.commit()
    _set_session_cookie(response, session.id)
    return OidcTokenOut(
        access_token=access_token,
        expires_at=access_token_expires_at(token_response),
        user=_user_out(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    session_id = request.cookies.get(settings.auth_session_cookie_name)
    if session_id:
        session = db.get(AuthSession, session_id)
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            record_audit_event(
                db,
                event_type="auth.session_revoked",
                actor_user_id=session.user_id,
                target_type="auth_session",
                target_id=session.id,
                action="logout",
                result="success",
                reason="OIDC server-managed session was revoked by logout.",
                correlation_id=_correlation_id(request),
                metadata_json=_session_audit_metadata(session),
            )
            db.commit()
    _clear_session_cookie(response)


def _validated_access_token(token_response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str):
        raise OIDCAuthenticationError("OIDC token response did not include an access token.")
    claims = decode_oidc_claims(access_token, get_settings())
    return access_token, claims


def _user_from_claims(db: Session, claims: dict[str, Any]) -> User:
    try:
        email = principal_email_from_claims(claims, get_settings())
    except OIDCAuthenticationError as exc:
        raise _unauthenticated("OIDC token does not map to a known identity.") from exc

    user = db.scalar(select(User).where(User.email == email))
    settings = get_settings()
    if not user and settings.oidc_auto_provision_users:
        role = db.scalar(
            select(Role).where(Role.name == settings.oidc_auto_provision_default_role)
        )
        if not role:
            raise _auth_configuration_error()
        user = User(
            email=email,
            display_name=_display_name_from_claims(claims, email),
        )
        user.roles.append(role)
        db.add(user)
        db.flush()

    if not user or not user.is_active:
        raise _unauthenticated("Unknown identity.")
    return user


def _display_name_from_claims(claims: dict[str, Any], email: str) -> str:
    for claim_name in ("name", "preferred_username", "upn", "email"):
        value = claims.get(claim_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return email


def _active_session_from_cookie(request: Request, db: Session) -> AuthSession:
    settings = get_settings()
    session_id = request.cookies.get(settings.auth_session_cookie_name)
    if not session_id:
        raise _unauthenticated("OIDC session cookie is required.")

    session = db.get(AuthSession, session_id)
    session_expired = session and _as_utc(session.expires_at) <= datetime.now(UTC)
    if not session or session.revoked_at is not None or session_expired:
        raise _unauthenticated("OIDC session is no longer active.")
    return session


def _set_session_cookie(response: Response, session_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.auth_session_cookie_name,
        session_id,
        httponly=True,
        secure=settings.auth_session_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_hours * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().auth_session_cookie_name, path="/", samesite="lax")


def _auth_configuration_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "AUTH_CONFIGURATION_ERROR",
            "message": "OIDC session authentication is not configured.",
        },
    )


def _unauthenticated(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHENTICATED", "message": message},
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=[role.name for role in user.roles],
    )


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", None) or "auth-session")


def _session_audit_metadata(session: AuthSession) -> dict[str, str]:
    return {
        "expires_at": session.expires_at.isoformat(),
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else "",
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

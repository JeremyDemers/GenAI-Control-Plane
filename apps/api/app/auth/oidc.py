from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx
import jwt
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError

from app.core.config import Settings
from app.core.security import RoleName


class OIDCAuthenticationError(Exception):
    """Raised when bearer-token credentials are missing or invalid."""


class OIDCConfigurationError(Exception):
    """Raised when production token validation is not configured."""


async def exchange_oidc_code(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    settings: Settings,
) -> dict[str, Any]:
    return await _post_oidc_token_request(
        settings,
        {
            "grant_type": "authorization_code",
            "client_id": settings.oidc_client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )


async def refresh_oidc_access_token(
    *,
    refresh_token: str,
    settings: Settings,
) -> dict[str, Any]:
    return await _post_oidc_token_request(
        settings,
        {
            "grant_type": "refresh_token",
            "client_id": settings.oidc_client_id,
            "refresh_token": refresh_token,
        },
    )


def access_token_expires_at(token_response: dict[str, Any]) -> datetime:
    expires_in = token_response.get("expires_in")
    if not isinstance(expires_in, int) or expires_in < 60:
        expires_in = 900
    return datetime.now(UTC) + timedelta(seconds=expires_in)


def bearer_token_from_authorization(authorization: str | None) -> str:
    if not authorization:
        raise OIDCAuthenticationError("Missing Authorization bearer token.")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise OIDCAuthenticationError("Expected Authorization: Bearer <token>.")
    return parts[1]


async def _post_oidc_token_request(
    settings: Settings,
    form_data: dict[str, str],
) -> dict[str, Any]:
    token_endpoint = effective_oidc_token_endpoint(settings)
    if not token_endpoint or not settings.oidc_client_id:
        raise OIDCConfigurationError(
            "OIDC_TOKEN_ENDPOINT or MICROSOFT_TENANT_ID, and OIDC_CLIENT_ID must be configured."
        )

    if settings.oidc_client_secret:
        form_data["client_secret"] = settings.oidc_client_secret

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(token_endpoint, data=form_data)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise OIDCAuthenticationError(_token_endpoint_error_message(exc.response)) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise OIDCAuthenticationError("OIDC token endpoint request failed.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise OIDCAuthenticationError("OIDC token response did not include an access token.")
    return payload


def decode_oidc_claims(token: str, settings: Settings) -> dict[str, Any]:
    issuer = effective_oidc_issuer(settings)
    audiences = effective_oidc_audiences(settings)
    if not issuer or not audiences:
        raise OIDCConfigurationError(
            "OIDC_ISSUER or MICROSOFT_TENANT_ID, and OIDC_AUDIENCE or OIDC_CLIENT_ID "
            "must be configured."
        )

    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise OIDCAuthenticationError("Invalid token header.") from exc

    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in settings.oidc_allowed_algorithms:
        raise OIDCAuthenticationError("Token signing algorithm is not allowed.")

    key = _verification_key(token, algorithm, settings)
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[algorithm],
            audience=audiences,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except InvalidTokenError as exc:
        raise OIDCAuthenticationError(_token_validation_error_message(exc)) from exc
    return claims


def principal_email_from_claims(claims: dict[str, Any], settings: Settings) -> str:
    for claim_name in settings.oidc_email_claims:
        claim_value = claims.get(claim_name)
        if isinstance(claim_value, str) and claim_value.strip():
            return claim_value.strip().lower()
    raise OIDCAuthenticationError("Token does not include a supported user email claim.")


def role_names_from_group_claims(claims: dict[str, Any], settings: Settings) -> set[str]:
    if not settings.oidc_group_role_map_json.strip():
        return set()

    group_role_map = _group_role_map(settings.oidc_group_role_map_json)
    claim_values = set()
    for claim_name in settings.oidc_group_claims:
        claim_values.update(_string_claim_values(claims.get(claim_name)))

    mapped_roles: set[str] = set()
    for claim_value in claim_values:
        mapped_roles.update(group_role_map.get(claim_value, set()))
    return mapped_roles


def _verification_key(token: str, algorithm: str, settings: Settings) -> Any:
    if algorithm.startswith("HS"):
        if algorithm == "HS256" and settings.oidc_hs256_secret:
            return settings.oidc_hs256_secret
        raise OIDCAuthenticationError("HMAC-signed token is not accepted.")

    if settings.oidc_jwks_json:
        return _key_from_static_jwks(token, settings.oidc_jwks_json)
    jwks_url = effective_oidc_jwks_url(settings)
    if jwks_url:
        try:
            return _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        except PyJWKClientError as exc:
            raise OIDCAuthenticationError("Unable to resolve token signing key.") from exc

    raise OIDCConfigurationError("OIDC_JWKS_URL or OIDC_JWKS_JSON must be configured.")


def effective_oidc_issuer(settings: Settings) -> str:
    if settings.oidc_issuer.strip():
        return settings.oidc_issuer.strip()
    tenant_id = _microsoft_tenant_id(settings)
    return f"https://login.microsoftonline.com/{tenant_id}/v2.0" if tenant_id else ""


def effective_oidc_audience(settings: Settings) -> str:
    if settings.oidc_audience.strip():
        return settings.oidc_audience.strip()
    return settings.oidc_client_id.strip() if _microsoft_tenant_id(settings) else ""


def effective_oidc_audiences(settings: Settings) -> list[str]:
    audiences = _comma_separated_values(effective_oidc_audience(settings))
    client_id = settings.oidc_client_id.strip()
    if _microsoft_tenant_id(settings) and client_id:
        audiences.extend([client_id, f"api://{client_id}"])
    return list(dict.fromkeys(audiences))


def effective_oidc_jwks_url(settings: Settings) -> str:
    if settings.oidc_jwks_url.strip():
        return settings.oidc_jwks_url.strip()
    tenant_id = _microsoft_tenant_id(settings)
    return (
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        if tenant_id
        else ""
    )


def effective_oidc_token_endpoint(settings: Settings) -> str:
    if settings.oidc_token_endpoint.strip():
        return settings.oidc_token_endpoint.strip()
    tenant_id = _microsoft_tenant_id(settings)
    return (
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        if tenant_id
        else ""
    )


def _microsoft_tenant_id(settings: Settings) -> str:
    return settings.microsoft_tenant_id.strip()


def _token_endpoint_error_message(response: httpx.Response) -> str:
    default = "OIDC token endpoint request failed."
    try:
        payload = response.json()
    except ValueError:
        return default

    if not isinstance(payload, dict):
        return default

    provider_error = _safe_token_error_field(payload.get("error"))
    provider_description = _safe_token_error_field(payload.get("error_description"))
    if provider_error and provider_description:
        return f"{provider_error}: {provider_description}"
    if provider_description:
        return provider_description
    if provider_error:
        return provider_error
    return default


def _safe_token_error_field(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:600]


def _token_validation_error_message(exc: InvalidTokenError) -> str:
    detail = " ".join(str(exc).split())
    error_name = exc.__class__.__name__
    if detail:
        return f"Bearer token failed validation: {error_name}: {detail}"
    return f"Bearer token failed validation: {error_name}"


def _comma_separated_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _key_from_static_jwks(token: str, jwks_json: str) -> Any:
    try:
        header = jwt.get_unverified_header(token)
        jwks = json.loads(jwks_json)
    except (InvalidTokenError, json.JSONDecodeError) as exc:
        raise OIDCConfigurationError("OIDC_JWKS_JSON is invalid.") from exc

    key_id = header.get("kid")
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list):
        raise OIDCConfigurationError("OIDC_JWKS_JSON must contain a keys list.")

    for jwk in keys:
        if not isinstance(jwk, dict):
            continue
        if key_id is None or jwk.get("kid") == key_id:
            return jwt.PyJWK.from_dict(jwk).key

    raise OIDCAuthenticationError("Bearer token signing key is not trusted.")


@lru_cache(maxsize=16)
def _group_role_map(map_json: str) -> dict[str, set[str]]:
    try:
        payload = json.loads(map_json)
    except json.JSONDecodeError as exc:
        raise OIDCConfigurationError("OIDC_GROUP_ROLE_MAP_JSON is invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise OIDCConfigurationError("OIDC_GROUP_ROLE_MAP_JSON must be a JSON object.")

    valid_roles = {role.value for role in RoleName}
    mapping: dict[str, set[str]] = {}
    for group_name, role_value in payload.items():
        if not isinstance(group_name, str) or not group_name:
            raise OIDCConfigurationError("OIDC group names must be non-empty strings.")
        role_names = _string_claim_values(role_value)
        invalid_roles = role_names - valid_roles
        if invalid_roles:
            raise OIDCConfigurationError(
                "OIDC_GROUP_ROLE_MAP_JSON contains unknown application roles."
            )
        mapping[group_name] = role_names
    return mapping


def _string_claim_values(value: Any) -> set[str]:
    if isinstance(value, str) and value.strip():
        return {value.strip()}
    if isinstance(value, list):
        return {item.strip() for item in value if isinstance(item, str) and item.strip()}
    return set()


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)

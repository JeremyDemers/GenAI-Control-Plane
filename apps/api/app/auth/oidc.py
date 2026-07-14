from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError

from app.core.config import Settings


class OIDCAuthenticationError(Exception):
    """Raised when bearer-token credentials are missing or invalid."""


class OIDCConfigurationError(Exception):
    """Raised when production token validation is not configured."""


def bearer_token_from_authorization(authorization: str | None) -> str:
    if not authorization:
        raise OIDCAuthenticationError("Missing Authorization bearer token.")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise OIDCAuthenticationError("Expected Authorization: Bearer <token>.")
    return parts[1]


def decode_oidc_claims(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.oidc_issuer or not settings.oidc_audience:
        raise OIDCConfigurationError("OIDC_ISSUER and OIDC_AUDIENCE must be configured.")

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
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except InvalidTokenError as exc:
        raise OIDCAuthenticationError("Bearer token failed validation.") from exc
    return claims


def principal_email_from_claims(claims: dict[str, Any], settings: Settings) -> str:
    for claim_name in settings.oidc_email_claims:
        claim_value = claims.get(claim_name)
        if isinstance(claim_value, str) and claim_value.strip():
            return claim_value.strip().lower()
    raise OIDCAuthenticationError("Token does not include a supported user email claim.")


def _verification_key(token: str, algorithm: str, settings: Settings) -> Any:
    if algorithm.startswith("HS"):
        if algorithm == "HS256" and settings.oidc_hs256_secret:
            return settings.oidc_hs256_secret
        raise OIDCAuthenticationError("HMAC-signed token is not accepted.")

    if settings.oidc_jwks_json:
        return _key_from_static_jwks(token, settings.oidc_jwks_json)
    if settings.oidc_jwks_url:
        try:
            return _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
        except PyJWKClientError as exc:
            raise OIDCAuthenticationError("Unable to resolve token signing key.") from exc

    raise OIDCConfigurationError("OIDC_JWKS_URL or OIDC_JWKS_JSON must be configured.")


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


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Access Control Center"
    environment: str = Field(default="local", validation_alias="APP_ENV")
    database_url: str = Field(
        default="sqlite:///./control_plane.db", validation_alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    dev_auth_enabled: bool = Field(default=True, validation_alias="DEV_AUTH_ENABLED")
    oidc_issuer: str = Field(default="", validation_alias="OIDC_ISSUER")
    oidc_audience: str = Field(default="", validation_alias="OIDC_AUDIENCE")
    oidc_jwks_url: str = Field(default="", validation_alias="OIDC_JWKS_URL")
    oidc_jwks_json: str = Field(default="", validation_alias="OIDC_JWKS_JSON")
    oidc_hs256_secret: str = Field(default="", validation_alias="OIDC_HS256_SECRET")
    oidc_allowed_algorithms: list[str] = Field(
        default=["RS256", "ES256", "HS256"],
        validation_alias="OIDC_ALLOWED_ALGORITHMS",
    )
    oidc_email_claims: list[str] = Field(
        default=["email", "preferred_username", "upn"],
        validation_alias="OIDC_EMAIL_CLAIMS",
    )
    oidc_group_claims: list[str] = Field(
        default=["groups", "roles"],
        validation_alias="OIDC_GROUP_CLAIMS",
    )
    oidc_group_role_map_json: str = Field(
        default="",
        validation_alias="OIDC_GROUP_ROLE_MAP_JSON",
    )
    oidc_auto_provision_users: bool = Field(
        default=False,
        validation_alias="OIDC_AUTO_PROVISION_USERS",
    )
    oidc_auto_provision_default_role: str = Field(
        default="employee",
        validation_alias="OIDC_AUTO_PROVISION_DEFAULT_ROLE",
    )
    oidc_auto_provision_roles: str = Field(
        default="",
        validation_alias="OIDC_AUTO_PROVISION_ROLES",
    )
    oidc_token_endpoint: str = Field(default="", validation_alias="OIDC_TOKEN_ENDPOINT")
    oidc_client_id: str = Field(default="", validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", validation_alias="OIDC_CLIENT_SECRET")
    microsoft_tenant_id: str = Field(default="", validation_alias="MICROSOFT_TENANT_ID")
    auth_session_cookie_name: str = Field(
        default="genai_cp_session",
        validation_alias="AUTH_SESSION_COOKIE_NAME",
    )
    auth_session_cookie_secure: bool = Field(
        default=False,
        validation_alias="AUTH_SESSION_COOKIE_SECURE",
    )
    auth_session_ttl_hours: int = Field(
        default=12,
        validation_alias="AUTH_SESSION_TTL_HOURS",
    )
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        validation_alias="CORS_ORIGINS",
    )
    provider_mode: str = Field(default="mock", validation_alias="PROVIDER_MODE")
    provider_live_operations_enabled: bool = Field(
        default=False,
        validation_alias="PROVIDER_LIVE_OPERATIONS_ENABLED",
    )
    aws_region: str = Field(default="", validation_alias="AWS_REGION")
    azure_tenant_id: str = Field(default="", validation_alias="AZURE_TENANT_ID")
    google_cloud_project: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")
    github_org: str = Field(default="", validation_alias="GITHUB_ORG")
    provider_webhook_secret: str = Field(
        default="local-provider-webhook-secret",
        validation_alias="PROVIDER_WEBHOOK_SECRET",
    )
    lifecycle_inline_execution: bool = Field(
        default=True,
        validation_alias="LIFECYCLE_INLINE_EXECUTION",
    )
    access_expiration_warning_days: int = Field(
        default=30,
        validation_alias="ACCESS_EXPIRATION_WARNING_DAYS",
    )
    rate_limit_requests_per_minute: int = Field(
        default=600,
        validation_alias="RATE_LIMIT_REQUESTS_PER_MINUTE",
    )

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

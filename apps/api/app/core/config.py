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

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

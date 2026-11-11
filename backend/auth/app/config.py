"""Validated Auth configuration. Compose supplies secrets from .env; no secret defaults."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    jwt_secret: str = Field(min_length=32)
    service_token: str = Field(min_length=24)
    jwt_issuer: str = "rental-auth"
    jwt_audience: str = "rental-admin"
    jwt_ttl_seconds: int = Field(default=3600, ge=300, le=86400)


@lru_cache(maxsize=1)
def get_settings() -> AuthSettings:
    """Read environment once per process; tests override this FastAPI dependency."""
    return AuthSettings()

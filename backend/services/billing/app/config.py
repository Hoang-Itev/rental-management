"""Billing configuration shared by the API, scheduler and publisher."""
from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tenant_url: AnyHttpUrl = 'http://tenant:8000'
    metering_url: AnyHttpUrl = 'http://metering:8000'
    service_token: SecretStr = Field(min_length=24)
    billing_http_timeout_seconds: float = Field(default=5, gt=0, le=60)
    billing_poll_seconds: int = Field(default=300, ge=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()

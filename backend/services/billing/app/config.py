"""Billing configuration shared by the API, scheduler and publisher."""
from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tenant_url: AnyHttpUrl = 'http://tenant:8000'
    metering_url: AnyHttpUrl = 'http://metering:8000'
    service_token: SecretStr = Field(min_length=24)
    billing_http_timeout_seconds: float = Field(default=5, gt=0, le=60)
    billing_poll_seconds: int = Field(default=300, ge=10)
    public_base_url: AnyHttpUrl = "http://localhost:8080"
    invoice_link_ttl_seconds: int = Field(default=259200, ge=60, le=604800)
    momo_partner_code: str = ""
    momo_access_key: SecretStr = SecretStr("")
    momo_secret_key: SecretStr = SecretStr("")
    momo_ipn_url: AnyHttpUrl | None = None
    momo_timeout_seconds: float = Field(default=30, ge=30, le=90)
    momo_reconcile_seconds: int = Field(default=300, ge=15)

    @field_validator("momo_ipn_url", mode="before")
    @classmethod
    def optional_ipn(cls, value):
        return value or None

    @field_validator("public_base_url")
    @classmethod
    def public_origin(cls, value: AnyHttpUrl):
        if value.path not in ("", "/") or value.query or value.fragment or value.username or value.password:
            raise ValueError("PUBLIC_BASE_URL must be an origin")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

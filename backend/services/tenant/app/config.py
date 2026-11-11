"""Tenant -> Room internal REST configuration; no user JWT is sent downstream."""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class TenantSettings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', case_sensitive=True)
    room_url: str = Field(default='http://room:8000', alias='ROOM_URL')
    service_token: str = Field(min_length=24, alias='SERVICE_TOKEN')
    room_timeout_seconds: float = Field(default=3.0, alias='ROOM_TIMEOUT_SECONDS', gt=0, le=15)

@lru_cache(maxsize=1)
def get_settings() -> TenantSettings:
    return TenantSettings()

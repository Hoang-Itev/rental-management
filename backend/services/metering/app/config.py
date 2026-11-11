"""P03 Metering settings; no eager connection at import time."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MeteringSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=True)
    service_token: str = Field(min_length=24, alias="SERVICE_TOKEN")


@lru_cache(maxsize=1)
def get_settings() -> MeteringSettings:
    return MeteringSettings()

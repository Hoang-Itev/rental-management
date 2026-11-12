from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    billing_url: AnyHttpUrl = "http://billing:8000"
    service_token: SecretStr = Field(min_length=24)
    owner_email: str = Field(default="owner@example.com", max_length=254, pattern=r"^[^\s@<>,;]+@[^\s@<>,;]+$")
    smtp_host: str = "mailpit"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_security: Literal["plain", "starttls", "tls"] = "plain"
    smtp_from: str = "billing@example.com"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    notification_timeout_seconds: float = Field(default=8, gt=0, le=30)
    notification_poll_seconds: float = Field(default=2, gt=0, le=60)
    notification_retry_seconds: int = Field(default=30, ge=1, le=3600)
    notification_max_attempts: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def validate_smtp(self):
        if bool(self.smtp_username) != bool(self.smtp_password.get_secret_value()):
            raise ValueError("SMTP username and password must be set together")
        if self.smtp_security == "plain" and self.smtp_username:
            raise ValueError("SMTP credentials require TLS")
        return self


@lru_cache
def get_settings():
    return Settings()

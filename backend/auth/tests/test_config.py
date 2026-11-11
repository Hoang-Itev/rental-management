import pytest
from pydantic import ValidationError

from app.config import AuthSettings


def test_defaults(settings):
    assert settings.jwt_issuer == "rental-auth"
    assert settings.jwt_audience == "rental-admin"
    assert settings.jwt_ttl_seconds == 3600


@pytest.mark.parametrize("changes", [
    {"jwt_secret": "short"},
    {"service_token": "short"},
    {"jwt_ttl_seconds": 299},
    {"jwt_ttl_seconds": 86401},
])
def test_invalid_settings_rejected(settings, changes):
    with pytest.raises(ValidationError):
        AuthSettings(**{**settings.model_dump(), **changes})


def test_reads_env_without_secret_defaults(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "c" * 48)
    monkeypatch.setenv("SERVICE_TOKEN", "d" * 40)
    monkeypatch.setenv("JWT_TTL_SECONDS", "900")
    configured = AuthSettings()
    assert configured.jwt_secret == "c" * 48
    assert configured.service_token == "d" * 40
    assert configured.jwt_ttl_seconds == 900

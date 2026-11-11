from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app import security, service
from app.schemas import UserPublic


def test_login_success_returns_jwt_and_safe_profile(fake_session, user, settings):
    response = service.login(fake_session, "OWNER@EXAMPLE.COM", "strong-correct-password", settings)
    assert response.token_type == "bearer"
    assert response.expires_in == 3600
    assert response.user == UserPublic.model_validate(user)
    assert security.decode_access_token(response.access_token, settings) == user.id
    assert fake_session.commits == 1
    assert isinstance(user.last_login_at, datetime) and user.last_login_at.tzinfo == timezone.utc
    assert "password_hash" not in response.model_dump_json()


def test_wrong_password_returns_same_error_and_no_write(fake_session, user, settings):
    with pytest.raises(service.AuthenticationRejected):
        service.login(fake_session, user.email, "wrong", settings)
    assert fake_session.commits == 0
    assert user.last_login_at is None


def test_missing_user_runs_dummy_hash_and_no_write(monkeypatch, fake_session, settings):
    fake_session.user = None
    called = []
    monkeypatch.setattr(security, "reject_unknown_user", lambda password: called.append(password))
    with pytest.raises(service.AuthenticationRejected):
        service.login(fake_session, "unknown@example.com", "wrong", settings)
    assert called == ["wrong"]
    assert fake_session.commits == 0


def test_inactive_user_cannot_login(fake_session, user, settings):
    user.is_active = False
    with pytest.raises(service.AuthenticationRejected):
        service.login(fake_session, user.email, "strong-correct-password", settings)
    assert fake_session.commits == 0


def test_current_user_accepts_valid_jwt(fake_session, user, settings):
    token = security.create_access_token(user.id, settings)
    assert service.current_user(fake_session, f"Bearer {token}", settings) is user


@pytest.mark.parametrize("header", [None, "Basic x", "Bearer bad", "Bearer"])
def test_current_user_rejects_missing_or_invalid_token(fake_session, settings, header):
    with pytest.raises(service.AuthenticationRejected):
        service.current_user(fake_session, header, settings)


def test_current_user_rechecks_database_active_status(fake_session, user, settings):
    token = security.create_access_token(user.id, settings)
    user.is_active = False
    with pytest.raises(service.AuthenticationRejected):
        service.current_user(fake_session, f"Bearer {token}", settings)


def test_current_user_rejects_deleted_or_unknown_user(fake_session, user, settings):
    token = security.create_access_token(uuid4(), settings)
    fake_session.user = None
    with pytest.raises(service.AuthenticationRejected):
        service.current_user(fake_session, f"Bearer {token}", settings)

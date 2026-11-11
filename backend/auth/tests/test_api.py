import json
from uuid import uuid4

import pytest

from app import security


def test_login_success(client, settings, fake_session, user):
    response = client.post("/api/v1/auth/login", json={"email": "OWNER@EXAMPLE.COM", "password": "strong-correct-password"})
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"
    data = response.json()
    assert set(data) == {"access_token", "token_type", "expires_in", "user"}
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == user.email
    assert "password_hash" not in response.text
    assert security.decode_access_token(data["access_token"], settings) == user.id
    assert fake_session.commits == 1


def test_invalid_login_is_generic_without_user_leak(client, fake_session):
    bad = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "UNAUTHORIZED"
    assert bad.headers["www-authenticate"] == "Bearer"
    fake_session.user = None
    unknown = client.post("/api/v1/auth/login", json={"email": "missing@example.com", "password": "wrong"})
    assert unknown.status_code == 401
    assert unknown.json()["message"] == bad.json()["message"]


@pytest.mark.parametrize("payload", [
    {"email": "bad-email", "password": "correct"},
    {"email": "user@example.com", "password": ""},
    {"email": "user@example.com", "password": "x" * 1025},
    {"email": "user@example.com"},
    {"email": "user@example.com", "password": "abc", "role": "ADMIN"},
])
def test_login_validation_rejects_bad_payload_without_leaking_password(client, payload):
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "password" not in response.text.lower()
    assert "x" * 50 not in response.text


def test_profile_requires_valid_bearer_and_returns_no_hash(client, settings, user):
    token = security.create_access_token(user.id, settings)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": user.email, "full_name": user.full_name, "is_active": True}
    assert "password_hash" not in response.text
    assert response.headers["cache-control"] == "no-store"
    for headers in ({}, {"Authorization": "Bearer invalid"}):
        bad = client.get("/api/v1/auth/me", headers=headers)
        assert bad.status_code == 401


def test_profile_rejects_deactivated_account(client, user, settings):
    token = security.create_access_token(user.id, settings)
    user.is_active = False
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_internal_verify_requires_service_secret(client, user, settings):
    token = security.create_access_token(user.id, settings)
    route = "/internal/v1/auth/verify"
    for bad in (None, "invalid"):
        headers = {"Authorization": f"Bearer {token}"}
        if bad is not None:
            headers["X-Service-Token"] = bad
        result = client.get(route, headers=headers)
        assert result.status_code == 403
        assert result.json()["code"] == "FORBIDDEN"


def test_internal_verify_returns_204_identity_only_with_both_tokens(client, user, settings):
    token = security.create_access_token(user.id, settings)
    headers = {"Authorization": f"Bearer {token}", "X-Service-Token": settings.service_token}
    response = client.get("/internal/v1/auth/verify", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["x-auth-user-id"] == str(user.id)
    assert client.get("/internal/v1/auth/verify", headers={**headers, "Authorization": "Bearer garbage"}).status_code == 401


def test_internal_verify_fails_on_deactivated_owner(client, user, settings):
    token = security.create_access_token(user.id, settings)
    user.is_active = False
    result = client.get("/internal/v1/auth/verify", headers={"Authorization": f"Bearer {token}", "X-Service-Token": settings.service_token})
    assert result.status_code == 401


def test_error_has_valid_correlation_id_and_no_request_echo(client):
    marker = str(uuid4())
    response = client.post("/api/v1/auth/login", headers={"X-Correlation-ID": marker}, json={"email": "oops", "password": "secret-leak-test"})
    assert response.status_code == 422
    assert response.json()["correlation_id"] == marker
    assert "secret-leak-test" not in response.text


def test_openapi_documents_two_public_auth_routes_only(client):
    spec = client.get("/openapi.json").json()
    assert "/api/v1/auth/login" in spec["paths"]
    assert "/api/v1/auth/me" in spec["paths"]
    assert "/internal/v1/auth/verify" not in spec["paths"]

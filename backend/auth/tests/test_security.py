from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from app import security


def test_argon2_hash_and_verification():
    stored = security.hash_password("correct-password")
    assert stored.startswith("$argon2id$")
    assert security.verify_password("correct-password", stored)
    assert not security.verify_password("incorrect", stored)
    assert not security.verify_password("correct-password", "invalid hash")
    assert "correct-password" not in stored


@pytest.mark.parametrize("password", ["", "x" * 1025])
def test_hash_password_rejects_invalid_lengths(password):
    with pytest.raises(ValueError):
        security.hash_password(password)


def test_dummy_hash_is_real_and_not_a_valid_password():
    # Unknown-account handling must do genuine Argon2 work without raising.
    assert security._DUMMY_HASH.startswith("$argon2id$")
    assert not security.verify_password("wrong", security._DUMMY_HASH)
    assert security.reject_unknown_user("wrong") is None


def test_service_token_must_match_exactly(settings):
    assert security.valid_service_token(settings.service_token, settings)
    assert not security.valid_service_token(None, settings)
    assert not security.valid_service_token("b" * 39, settings)
    assert not security.valid_service_token("wrong", settings)


@pytest.mark.parametrize("value", [None, "", "Basic hello", "Bearer", "Bearer a b", "Bearer " + "a" * 5000])
def test_invalid_bearer_headers(value):
    with pytest.raises(security.InvalidAccessToken):
        security.bearer_token(value)


def test_bearer_header_case_and_whitespace():
    assert security.bearer_token("bEaReR  hello ") == "hello"


def test_token_roundtrip_and_unique_jti(settings):
    identity = uuid4()
    token1 = security.create_access_token(identity, settings)
    token2 = security.create_access_token(identity, settings)
    assert token1 != token2
    assert security.decode_access_token(token1, settings) == identity
    claims = jwt.decode(token1, settings.jwt_secret, algorithms=["HS256"],
                        audience=settings.jwt_audience, issuer=settings.jwt_issuer)
    assert claims["typ"] == "access"
    assert int(claims["exp"] - claims["iat"]) == 3600


def test_expired_and_future_token_rejected(settings):
    identity = uuid4()
    expired = security.create_access_token(identity, settings, now=datetime.now(timezone.utc) - timedelta(hours=2))
    future = security.create_access_token(identity, settings, now=datetime.now(timezone.utc) + timedelta(hours=2))
    for token in (expired, future):
        with pytest.raises(security.InvalidAccessToken):
            security.decode_access_token(token, settings)


def test_naive_datetime_rejected(settings):
    with pytest.raises(ValueError):
        security.create_access_token(uuid4(), settings, now=datetime(2026, 1, 1))


def test_tampered_wrong_secret_wrong_issuer_audience_and_algorithm(settings):
    identity = uuid4()
    token = security.create_access_token(identity, settings)
    other = settings.model_copy(update={"jwt_secret": "other" * 12})
    wrong_issuer = settings.model_copy(update={"jwt_issuer": "other"})
    wrong_audience = settings.model_copy(update={"jwt_audience": "other"})
    for scenario in (other, wrong_issuer, wrong_audience):
        with pytest.raises(security.InvalidAccessToken):
            security.decode_access_token(token, scenario)
    # Even an explicitly HS384-signed token must fail: accepted algorithms = HS256 only.
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"],
                         audience=settings.jwt_audience, issuer=settings.jwt_issuer)
    for forged in (
        jwt.encode(payload, settings.jwt_secret, algorithm="HS384"),
        jwt.encode({**payload, "typ": "refresh"}, settings.jwt_secret, algorithm="HS256"),
        jwt.encode({**payload, "sub": "not-a-uuid"}, settings.jwt_secret, algorithm="HS256"),
        jwt.encode({**payload, "jti": "bad-id"}, settings.jwt_secret, algorithm="HS256"),
        jwt.encode({k: v for k, v in payload.items() if k != "exp"}, settings.jwt_secret, algorithm="HS256"),
    ):
        with pytest.raises(security.InvalidAccessToken):
            security.decode_access_token(forged, settings)


def test_malformed_token_is_rejected(settings):
    with pytest.raises(security.InvalidAccessToken):
        security.decode_access_token("not.jwt.token", settings)

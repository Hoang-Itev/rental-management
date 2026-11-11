"""Fixtures exercise API without a running DB; PostgreSQL is tested in gateway E2E."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import AuthSettings, get_settings
from app.db import get_db
from app.main import app
from app.security import hash_password


class FakeSession:
    def __init__(self, user=None):
        self.user = user
        self.added = []
        self.commits = 0
        self.last_query = None

    def scalar(self, query):
        self.last_query = query
        return self.user

    def get(self, model, identifier):
        self.last_query = (model, identifier)
        if self.user and self.user.id == identifier:
            return self.user
        return None

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1


@pytest.fixture
def settings():
    return AuthSettings(jwt_secret="a" * 48, service_token="b" * 40)


@pytest.fixture
def user():
    return SimpleNamespace(
        id=uuid4(), email="owner@example.com", full_name="Demo Owner",
        password_hash=hash_password("strong-correct-password"),
        is_active=True, last_login_at=None,
    )


@pytest.fixture
def fake_session(user):
    return FakeSession(user)


@pytest.fixture
def client(settings, fake_session):
    app.dependency_overrides[get_db] = lambda: fake_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

from unittest.mock import MagicMock

from sqlalchemy.exc import OperationalError

from app import main


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_when_migrated(monkeypatch, client):
    connection = MagicMock()
    connection.execute.return_value.scalar_one_or_none.return_value = "auth_v3_001"
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_without_migration_is_503(monkeypatch, client):
    connection = MagicMock()
    connection.execute.return_value.scalar_one_or_none.return_value = None
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"


def test_ready_database_error_is_503(monkeypatch, client):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("connection error"))
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    assert client.get("/ready").status_code == 503


def test_bogus_correlation_id_gets_new_uuid(client):
    response = client.post("/api/v1/auth/login", headers={"X-Correlation-ID": "not-a-uuid"}, json={})
    assert response.status_code == 422
    import uuid
    uuid.UUID(response.json()["correlation_id"])

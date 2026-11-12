from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


def test_missing_email_job_has_standard_error():
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(get=lambda *_, **__: None)
    try:
        with TestClient(app) as http:
            response = http.get(f"/api/v1/email-jobs/{uuid4()}")
            assert response.status_code == 404
            assert response.json()["code"] == "EMAIL_JOB_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_db)

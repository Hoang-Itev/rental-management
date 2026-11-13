from datetime import datetime

from fastapi.testclient import TestClient

from app.api import get_invoice_service
from app.main import app
from app.scheduler import last_due_month
from app.service import InvoiceService, VN


def test_reject_open_month_before_database_access():
    app.dependency_overrides[get_invoice_service] = lambda: InvoiceService(None, None)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/billing-runs", json={
                "billing_month": datetime.now(VN).date().replace(day=1).isoformat(),
            })
            assert response.status_code == 409
            assert response.json()["code"] == "BILLING_RUN_CONFLICT"
            assert client.post("/api/v1/billing-runs", json={"billing_month": "2024-11-02"}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_monthly_schedule_uses_vietnam_time_and_catches_up():
    from datetime import date

    assert last_due_month(datetime(2025, 1, 1, 1, 59, tzinfo=VN)) == date(2024, 11, 1)
    assert last_due_month(datetime(2025, 1, 1, 2, tzinfo=VN)) == date(2024, 12, 1)
    assert last_due_month(datetime(2025, 1, 10, 2, tzinfo=VN)) == date(2024, 12, 1)


def test_p13_request_schemas_reject_blank_reason_and_zero_adjustment():
    import pytest
    from pydantic import ValidationError

    from app.schemas import AdjustmentCreate, InvoiceReason, ResolveAdjustment

    with pytest.raises(ValidationError):
        InvoiceReason(reason="   ")
    with pytest.raises(ValidationError):
        AdjustmentCreate(reason="Corrected rate", amount_delta=0)
    with pytest.raises(ValidationError):
        ResolveAdjustment(status="OPEN", resolution_note="Still open")


def test_checkout_explains_pending_without_url_and_preserves_ready_response():
    from types import SimpleNamespace
    from uuid import uuid4
    from app.api_webhook import get_payment_service
    from app.payment import PaymentService

    attempt = SimpleNamespace(id=uuid4(), status="PENDING", pay_url=None, expires_at=None)
    service = PaymentService(None, SimpleNamespace(settings=SimpleNamespace(momo_reconcile_seconds=300)))
    app.dependency_overrides[get_payment_service] = lambda: SimpleNamespace(
        checkout=lambda token, key: service.view(attempt, reused=True))
    try:
        with TestClient(app) as client:
            endpoint = "/public/v1/invoices/" + "a" * 43 + "/payments/momo"
            response = client.post(endpoint)
            assert response.status_code == 202
            assert response.headers["Retry-After"] == "300"
            assert response.headers["Cache-Control"] == "no-store"
            assert response.json()["checkout_status"] == "RECONCILING"
            assert response.json()["retry_after_seconds"] == 300
            assert "pay_url" not in response.json()
            attempt.pay_url = "https://test-payment.momo.vn/gateway/pay?t=test"
            response = client.post(endpoint)
            assert response.status_code == 200
            assert response.json()["checkout_status"] == "READY"
            assert response.json()["pay_url"] == attempt.pay_url
            assert "Retry-After" not in response.headers
            attempt.status = "SUCCESS"
            response = client.post(endpoint)
            assert response.status_code == 200
            assert response.json()["checkout_status"] == "PAID"
            assert "pay_url" not in response.json()
    finally:
        app.dependency_overrides.pop(get_payment_service)

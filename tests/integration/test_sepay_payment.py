"""SePay Sandbox contract: signed browser form + authenticated IPN on real PostgreSQL.

Runs only on disposable test DB via the existing momo-payments integration suite.
No calls to SePay or production bank APIs are made.
"""
import hashlib
import hmac
import json
import os
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from secrets import token_urlsafe
from uuid import UUID, uuid4

import pytest

if os.getenv("P11_EPHEMERAL_TEST") != "1":
    pytest.skip("SePay tests require a disposable PostgreSQL database", allow_module_level=True)

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api_webhook import get_payment_service, get_sepay_payment_service
from app.config import Settings
from app.db import get_sessionmaker
from app.main import app
from app.models import Invoice, InvoiceAccessToken, OutboxEvent, PaymentAttempt, PaymentWebhookReceipt
from app.momo import MomoClient
from app.payment import PaymentService, utcnow
from app.sepay import SIGNED_FIELDS, SePayGateway
from app.sepay_payment import SePayPaymentService
from app.service import hash_link_token

MERCHANT_SECRET = "spsk_test_demo_mock_merchant_private"
IPN_SECRET = "sepay-different-ipn-secret-keep-private"


@pytest.fixture
def checkout():
    sessions = get_sessionmaker()
    invoice_id = uuid4()
    token = token_urlsafe(32)
    with sessions.begin() as db:
        db.add(Invoice(
            id=invoice_id, invoice_code="SEPAY-" + invoice_id.hex, contract_id=uuid4(), room_id=uuid4(),
            invoice_type="PERIODIC", billing_month=date(2026, 10, 1),
            period_start=date(2026, 10, 1), period_end=date(2026, 11, 1),
            status="ISSUED", total_amount=1234567, due_date=date(2026, 11, 5),
            issued_at=utcnow(), tenant_name_snapshot="Khách demo",
            tenant_email_snapshot="sepay@example.com", room_code_snapshot="A101",
        ))
        db.flush()
        db.add(InvoiceAccessToken(
            invoice_id=invoice_id, token_hash=hash_link_token(token),
            expires_at=utcnow() + timedelta(hours=1),
        ))
    settings = Settings(
        service_token="unit-test-only-internal-service-token",
        sepay_merchant_id="SP-TEST-INTEGRATION", sepay_secret_key=MERCHANT_SECRET,
        sepay_ipn_secret_key=IPN_SECRET,
        momo_partner_code="TEST-MOMO", momo_access_key="momo-access",
        momo_secret_key="momo-secret", momo_ipn_url="https://example.com/webhooks/momo/ipn",
    )
    app.dependency_overrides[get_sepay_payment_service] = (
        lambda: SePayPaymentService(sessions, SePayGateway(settings)))
    app.dependency_overrides[get_payment_service] = (
        lambda: PaymentService(sessions, MomoClient(None, settings)))
    try:
        with TestClient(app) as api:
            yield sessions, api, invoice_id, f"/public/v1/invoices/{token}"
    finally:
        app.dependency_overrides.pop(get_sepay_payment_service, None)
        app.dependency_overrides.pop(get_payment_service, None)


def sepay_notification(attempt, **changes):
    payload = {
        "timestamp": 1794539515, "notification_type": "ORDER_PAID",
        "order": {
            "order_invoice_number": attempt.order_id, "order_id": "SP-" + attempt.id.hex,
            "order_status": "CAPTURED", "order_currency": "VND",
            "order_amount": str(attempt.amount) + ".00",
        },
        "transaction": {
            "transaction_id": attempt.id.hex, "transaction_status": "APPROVED",
            "transaction_amount": str(attempt.amount), "transaction_currency": "VND",
            "transaction_type": "PAYMENT", "payment_method": "BANK_TRANSFER",
        },
        "customer": {"customer_id": "C001"},
    }
    for name, value in changes.items():
        if name.startswith("order_"):
            payload["order"][name[6:]] = value
        elif name.startswith("transaction_"):
            payload["transaction"][name[12:]] = value
        else:
            payload[name] = value
    return payload


def test_sepay_checkout_is_reused_and_matches_official_signature(checkout):
    sessions, api, invoice_id, url = checkout
    endpoint = url + "/payments/sepay"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda _: api.post(endpoint, headers={"Idempotency-Key": "sepay-demo-1"}), range(2)))
    assert all(r.status_code == 200 for r in responses)
    a, b = (r.json() for r in responses)
    assert a["payment_attempt_id"] == b["payment_attempt_id"]
    assert {a["reused_pending_attempt"], b["reused_pending_attempt"]} == {False, True}
    assert a["action_url"] == "https://pay-sandbox.sepay.vn/v1/checkout/init"
    assert a["method"] == "POST"
    fields = a["fields"]
    assert fields["merchant"] == "SP-TEST-INTEGRATION"
    assert fields["payment_method"] == "BANK_TRANSFER"
    assert fields["order_amount"] == "1234567" and fields["currency"] == "VND"
    canonical = ",".join(f"{n}={fields[n]}" for n in SIGNED_FIELDS if n in fields)
    expected = b64encode(hmac.new(MERCHANT_SECRET.encode(), canonical.encode(), hashlib.sha256).digest()).decode()
    assert fields["signature"] == expected
    assert "sepay-different-ipn-secret" not in json.dumps(fields)
    assert "spsk_test_" not in json.dumps(fields)
    with sessions() as db:
        attempts = db.scalars(select(PaymentAttempt).where(PaymentAttempt.invoice_id == invoice_id)).all()
        assert len(attempts) == 1 and attempts[0].provider == "SEPAY"


def test_sepay_ipn_auth_validation_replay_and_single_payment_event(checkout):
    sessions, api, invoice_id, url = checkout
    data = api.post(url + "/payments/sepay").json()
    with sessions() as db:
        attempt = db.get(PaymentAttempt, UUID(data["payment_attempt_id"]))
    webhook = "/webhooks/sepay/ipn"
    body = sepay_notification(attempt)
    assert api.post(webhook, json=body).status_code == 401
    assert api.post(webhook, json=body, headers={"X-Secret-Key": "bad"}).status_code == 401
    good = {"X-Secret-Key": IPN_SECRET}
    assert api.post(webhook, json=sepay_notification(attempt, order_order_amount="999.00"), headers=good).status_code == 409
    assert api.post(webhook, json=sepay_notification(attempt, order_order_invoice_number="wrong"), headers=good).status_code == 404
    assert api.post(webhook, json=sepay_notification(attempt, transaction_transaction_amount=123.45), headers=good).status_code == 422
    assert api.get("/public/v1/payments/sepay/return?result=success").status_code == 200
    assert api.get(url).json()["status"] == "ISSUED"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: api.post(webhook, json=body, headers=good), range(2)))
    assert all(r.status_code == 200 and r.json() == {"success": True} for r in responses)
    assert api.get(url).json()["status"] == "PAID"
    paid = api.post(url + "/payments/sepay").json()
    assert paid["checkout_status"] == "PAID" and "fields" not in paid
    with sessions() as db:
        receipts = db.scalars(select(PaymentWebhookReceipt.processing_result).where(
            PaymentWebhookReceipt.order_id == attempt.order_id)).all()
        assert set(receipts) == {"PROCESSED", "DUPLICATE", "AMOUNT_MISMATCH"}
        event = db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id == invoice_id)).one()
        assert event.event_type == "PaymentSucceeded"
        assert event.payload["data"]["paid_amount"] == attempt.amount
        assert db.scalar(select(func.count()).select_from(PaymentAttempt).where(
            PaymentAttempt.invoice_id == invoice_id)) == 1


def test_pending_provider_blocks_switching_to_momo(checkout):
    _, api, _, url = checkout
    session = api.post(url + "/payments/sepay").json()
    response = api.post(url + "/payments/momo")
    assert response.status_code == 409
    assert response.json()["code"] == "PAYMENT_PROVIDER_CONFLICT"
    assert api.post(url + "/payments/sepay").json()["payment_attempt_id"] == session["payment_attempt_id"]


def test_void_cannot_mark_invoice_paid_and_late_success_requires_review(checkout):
    sessions, api, _, url = checkout
    first = api.post(url + "/payments/sepay").json()
    with sessions() as db:
        attempt = db.get(PaymentAttempt, UUID(first["payment_attempt_id"]))
    hdr = {"X-Secret-Key": IPN_SECRET}
    void = sepay_notification(attempt, notification_type="TRANSACTION_VOID")
    assert api.post("/webhooks/sepay/ipn", json=void, headers=hdr).status_code == 200
    with sessions() as db:
        assert db.get(PaymentAttempt, attempt.id).status == "FAILED"
    assert api.post(url + "/payments/sepay", headers={"Idempotency-Key": "next"}).status_code == 200
    assert api.post("/webhooks/sepay/ipn", json=sepay_notification(attempt), headers=hdr).status_code == 409
    assert api.get(url).json()["status"] == "ISSUED"

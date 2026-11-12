"""P11 PostgreSQL payment transitions with MoMo HTTP at a deterministic test boundary."""
import asyncio
import hashlib
import hmac
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from secrets import token_urlsafe
from uuid import UUID, uuid4

import pytest

if os.getenv("P11_EPHEMERAL_TEST") != "1":
    pytest.skip("P11 requires a disposable database", allow_module_level=True)

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api_webhook import get_payment_service
from app.config import Settings
from app.db import get_sessionmaker
from app.main import app
from app.messaging import RabbitPublisher, publish_pending
from app.models import Invoice, InvoiceAccessToken, OutboxEvent, PaymentAttempt, PaymentWebhookReceipt
from app.momo import MomoClient
from app.payment import PaymentService, utcnow
from app.service import hash_link_token

ACCESS = "sandbox-test-access"
SECRET = "sandbox-test-secret"
PARTNER = "P11_TEST_PARTNER"


def signed_ipn(attempt, **changes):
    payload = {
        "partnerCode": PARTNER, "orderId": attempt.order_id, "requestId": attempt.request_id,
        "amount": attempt.amount, "resultCode": 0, "transId": int(attempt.id.hex[:13], 16),
        "message": "Thành công", "orderInfo": f"Invoice payment {attempt.order_id}",
        "orderType": "momo_wallet", "payType": "napas", "responseTime": 1794000000000, "extraData": "",
    }
    payload.update(changes)
    payload["signature"] = hmac.new(
        SECRET.encode(), "&".join([f"accessKey={ACCESS}", *(f"{k}={v}" for k, v in sorted(payload.items()))]).encode(),
        hashlib.sha256,
    ).hexdigest()
    return payload


@pytest.fixture
def fixture():
    sessions = get_sessionmaker()
    token = token_urlsafe(32)
    invoice_id = uuid4()
    with sessions.begin() as db:
        db.add(Invoice(
            id=invoice_id, invoice_code=f"P11-{invoice_id.hex}", contract_id=uuid4(), room_id=uuid4(),
            invoice_type="PERIODIC", billing_month=date(2026, 10, 1), period_start=date(2026, 10, 1),
            period_end=date(2026, 11, 1), status="ISSUED", total_amount=1500000, due_date=date(2026, 11, 5),
            issued_at=utcnow(), tenant_name_snapshot="Người thuê", tenant_email_snapshot="tenant@example.com",
            room_code_snapshot="A101",
        ))
        db.flush()
        db.add(InvoiceAccessToken(invoice_id=invoice_id, token_hash=hash_link_token(token),
                                  expires_at=utcnow() + timedelta(hours=1)))
    state = {"create_calls": 0, "timeout": False, "query_code": 1000, "query_trans_id": int(invoice_id.hex[:13], 16)}

    def gateway(request):
        data = json.loads(request.content)
        # Independent oracle for provider canonicalization.
        if request.url.path.endswith("/create"):
            names = ("amount", "extraData", "ipnUrl", "orderId", "orderInfo", "partnerCode",
                     "redirectUrl", "requestId", "requestType")
            state["create_calls"] += 1
            assert data["requestType"] == "payWithATM" and data["amount"] == 1500000
            assert token not in json.dumps(data)
            if state["timeout"]:
                raise httpx.ReadTimeout("Sandbox timeout", request=request)
            extras = {"resultCode": 0, "payUrl": "https://test-payment.momo.vn/gateway/pay?t=test"}
        else:
            assert request.url.path.endswith("/query")
            names = ("orderId", "partnerCode", "requestId")
            extras = {"resultCode": state["query_code"], "transId": state["query_trans_id"]}
        raw = f"accessKey={ACCESS}&" + "&".join(f"{key}={data[key]}" for key in names)
        assert data["signature"] == hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        return httpx.Response(200, json={
            "partnerCode": PARTNER, "orderId": data["orderId"], "requestId": data["requestId"],
            "amount": 1500000, **extras,
        })

    settings = Settings(
        service_token="disposable-p11-test-token-value",
        momo_partner_code=PARTNER, momo_access_key=ACCESS, momo_secret_key=SECRET,
        momo_ipn_url="https://gateway.example.com/webhooks/momo/ipn",
    )
    with httpx.Client(transport=httpx.MockTransport(gateway)) as http:
        app.dependency_overrides[get_payment_service] = lambda: PaymentService(sessions, MomoClient(http, settings))
        try:
            with TestClient(app) as api:
                yield sessions, api, invoice_id, f"/public/v1/invoices/{token}", state
        finally:
            app.dependency_overrides.pop(get_payment_service)


def attempt_row(sessions, attempt_id):
    with sessions() as db:
        return db.get(PaymentAttempt, UUID(attempt_id))


def test_signed_ipn_rejects_mismatch_and_is_idempotent(fixture):
    sessions, api, invoice_id, url, state = fixture
    endpoint = url + "/payments/momo"
    headers = {"Idempotency-Key": "checkout-invoice"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: api.post(endpoint, headers=headers), range(2)))
    assert [result.status_code for result in results] == [200, 200]
    attempt_ids = {result.json()["payment_attempt_id"] for result in results}
    assert len(attempt_ids) == state["create_calls"] == 1
    assert any(result.json().get("pay_url") for result in results)
    attempt = attempt_row(sessions, attempt_ids.pop())

    webhook = "/webhooks/momo/ipn"
    invalid = signed_ipn(attempt)
    invalid["signature"] = "0" * 64
    assert api.post(webhook, json=invalid).status_code == 403
    assert api.post(webhook, json=signed_ipn(attempt, amount=1)).status_code == 409
    assert api.post(webhook, json=signed_ipn(attempt, requestId="wrong")).status_code == 404
    assert api.get(url).json()["status"] == "ISSUED"
    assert api.get("/public/v1/payments/momo/return?resultCode=0").status_code == 200
    assert api.get(url).json()["status"] == "ISSUED"
    signed = signed_ipn(attempt)
    with ThreadPoolExecutor(max_workers=2) as pool:
        callbacks = list(pool.map(lambda _: api.post(webhook, json=signed), range(2)))
    assert all(response.status_code == 204 and not response.content for response in callbacks)
    assert api.get(url).json()["status"] == "PAID"
    assert api.post(endpoint).json()["status"] == "SUCCESS"
    with sessions() as db:
        receipts = db.scalars(select(PaymentWebhookReceipt.processing_result)
                              .where(PaymentWebhookReceipt.order_id == attempt.order_id)).all()
        assert set(receipts) == {"INVALID_SIGNATURE", "AMOUNT_MISMATCH", "UNKNOWN_ORDER", "PROCESSED", "DUPLICATE"}
        event = db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id == invoice_id)).one()
        assert event.event_type == "PaymentSucceeded"
        assert event.payload["data"]["paid_amount"] == 1500000
        assert event.payload["data"]["payment_attempt_id"] == str(attempt.id)
        assert db.scalar(select(func.count()).select_from(PaymentAttempt)
                         .where(PaymentAttempt.invoice_id == invoice_id)) == 1
    if os.getenv("P11_RABBITMQ_TEST") == "1":
        asyncio.run(check_broker(sessions, event.id))


def test_timeout_keeps_pending_and_query_completes(fixture):
    sessions, api, invoice_id, url, state = fixture
    state["timeout"] = True
    endpoint = url + "/payments/momo"
    first = api.post(endpoint).json()
    assert first["status"] == "PENDING" and "pay_url" not in first
    assert api.post(endpoint).json()["payment_attempt_id"] == first["payment_attempt_id"]
    assert state["create_calls"] == 1
    query = {"payment_attempt_id": first["payment_attempt_id"]}
    reconcile = "/api/v1/jobs/payments/reconcile/run"
    assert api.post(reconcile, json=query).json()["still_pending_count"] == 1
    assert api.get(url).json()["status"] == "ISSUED"
    state["query_code"] = 0
    assert api.post(reconcile, json=query).json()["succeeded_count"] == 1
    assert api.get(url).json()["status"] == "PAID"
    assert api.post(reconcile, json=query).json()["checked_count"] == 0
    with sessions() as db:
        assert db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id == invoice_id)).one()


def test_late_success_on_expired_attempt_requires_query(fixture):
    sessions, api, invoice_id, url, state = fixture
    session = api.post(url + "/payments/momo").json()
    attempt = attempt_row(sessions, session["payment_attempt_id"])
    webhook = "/webhooks/momo/ipn"
    assert api.post(webhook, json=signed_ipn(attempt, resultCode=1005)).status_code == 204
    assert attempt_row(sessions, session["payment_attempt_id"]).status == "EXPIRED"
    assert api.post(webhook, json=signed_ipn(attempt, transId=state["query_trans_id"])).status_code == 204
    assert api.get(url).json()["status"] == "ISSUED"
    with sessions() as db:
        assert db.scalar(select(PaymentWebhookReceipt.id)
                         .where(PaymentWebhookReceipt.payment_attempt_id == attempt.id,
                                PaymentWebhookReceipt.processing_result == "RECONCILIATION_REQUIRED"))
    state["query_code"] = 0
    response = api.post("/api/v1/jobs/payments/reconcile/run",
                        json={"payment_attempt_id": session["payment_attempt_id"]})
    assert response.json()["succeeded_count"] == 1
    assert api.get(url).json()["status"] == "PAID"
    with sessions() as db:
        assert db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id == invoice_id)).one()


async def check_broker(sessions, event_id):
    import aio_pika

    connection = await aio_pika.connect(os.environ["RABBITMQ_URL"], timeout=8)
    async with connection:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        publisher = RabbitPublisher(channel)
        await publisher.start()
        assert await publish_pending(sessions, publisher) == (1, False)
        queue = await channel.get_queue("notification.events.q")
        message = await queue.get(timeout=5)
        async with message.process():
            assert message.routing_key == "payment.succeeded.v1"
            assert message.message_id == str(event_id)

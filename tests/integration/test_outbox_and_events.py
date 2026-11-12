"""P10 browser-link, RabbitMQ and SMTP checks against disposable Compose services."""
import asyncio
from contextlib import contextmanager
import json
import os
import re
import socket
import subprocess
import sys
import time
from uuid import uuid4

import pytest

if os.getenv("P10_EPHEMERAL_TEST") != "1":
    pytest.skip("P10 requires a disposable Compose project", allow_module_level=True)

import aio_pika
import httpx
from sqlalchemy import create_engine, select, text

from app.db import get_sessionmaker
from app.models import EmailJob

MAILPIT = "http://mailpit:8025"


def wait_for(check, description, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.2)
    pytest.fail(f"Timed out waiting for {description}")


@contextmanager
def running_worker(**overrides):
    worker = subprocess.Popen([sys.executable, "-m", "app.worker"], env={**os.environ, **overrides})
    try:
        yield
        assert worker.poll() is None
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()


def seed_invoice(engine):
    invoice_id, event_id = uuid4(), uuid4()
    payload = {
        "event_id": str(event_id), "event_type": "InvoiceIssued", "event_version": 1,
        "occurred_at": "2026-11-02T00:00:00Z", "correlation_id": str(event_id),
        "aggregate_id": str(invoice_id),
        "data": {
            "invoice_id": str(invoice_id), "invoice_code": f"P10-{invoice_id.hex[:12]}",
            "tenant_name": "Người thuê A1", "room_code": "A1",
            "recipient_email": "tenant-p10@example.com", "total_amount": 1500000,
            "period_start": "2026-10-01", "period_end_exclusive": "2026-11-01",
            "due_date": "2026-11-05",
        },
    }
    with engine.begin() as db:
        db.execute(text("""
            INSERT INTO invoices (id, invoice_code, contract_id, room_id, invoice_type,
                                  billing_month, period_start, period_end, status, total_amount,
                                  due_date, issued_at, tenant_name_snapshot, tenant_email_snapshot,
                                  room_code_snapshot)
            VALUES (:invoice, :code, :contract, :room, 'PERIODIC', '2026-10-01',
                    '2026-10-01', '2026-11-01', 'ISSUED', 1500000, '2026-11-05', now(),
                    'Người thuê A1', 'tenant-p10@example.com', 'A1')
        """), {"invoice": invoice_id, "code": payload["data"]["invoice_code"],
               "contract": uuid4(), "room": uuid4()})
        db.execute(text("""
            INSERT INTO invoice_items (invoice_id, item_type, description, quantity, unit, unit_price, amount)
            VALUES (:invoice, 'RENT', 'Tiền phòng', 1, 'MONTH', 1500000, 1500000)
        """), {"invoice": invoice_id})
        db.execute(text("""
            INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, correlation_id)
            VALUES (:event, 'Invoice', :invoice, 'InvoiceIssued', CAST(:payload AS jsonb), :event)
        """), {"event": event_id, "invoice": invoice_id, "payload": json.dumps(payload)})
    return invoice_id, event_id, payload


async def publish_duplicate(payload):
    connection = await aio_pika.connect(os.environ["RABBITMQ_URL"], timeout=8)
    async with connection:
        channel = await connection.channel(on_return_raises=True)
        exchange = await channel.get_exchange("rental.domain.v1")
        await exchange.publish(aio_pika.Message(json.dumps(payload).encode()), routing_key="invoice.issued.v1")


def test_invoice_event_retries_smtp_and_public_link_expires():
    billing_db = create_engine(os.environ["P10_BILLING_DATABASE_URL"])
    invoice_id, event_id, payload = seed_invoice(billing_db)
    sessions = get_sessionmaker()

    def get_job():
        with sessions() as db:
            return db.scalars(select(EmailJob).where(EmailJob.source_event_id == event_id)).one_or_none()

    def was_published():
        with billing_db.connect() as db:
            return db.scalar(text("SELECT published_at FROM outbox_events WHERE id=:id"), {"id": event_id})

    try:
        wait_for(was_published, "Billing outbox publisher")
        asyncio.run(publish_duplicate(payload))
        with socket.socket() as refused:
            refused.bind(("127.0.0.1", 0))
            with running_worker(SMTP_HOST="127.0.0.1", SMTP_PORT=str(refused.getsockname()[1]),
                                NOTIFICATION_RETRY_SECONDS="120"):
                def scheduled_retry():
                    job = get_job()
                    return job if job and job.attempt_count == 1 and job.next_attempt_at else None

                job = wait_for(scheduled_retry, "SMTP failure and retry schedule")
                assert job.status == "PENDING" and job.last_error == "SMTP delivery failed"
        with sessions.begin() as db:
            db.execute(text("UPDATE email_jobs SET next_attempt_at = now() WHERE id=:id"), {"id": job.id})

        with running_worker(SMTP_HOST="mailpit", SMTP_PORT="1025"):
            def sent():
                job = get_job()
                return job if job and job.status == "SENT" else None

            job = wait_for(sent, "successful SMTP retry")
            assert job.attempt_count == 2 and job.last_error is None
            assert "http://" not in json.dumps(job.template_data)
            with httpx.Client(timeout=8, trust_env=False) as http:
                messages = http.get(f"{MAILPIT}/api/v1/messages").raise_for_status().json()
                assert messages["total"] == 1
                message = http.get(f"{MAILPIT}/api/v1/message/{messages['messages'][0]['ID']}").raise_for_status().json()
                assert "tenant-p10@example.com" in json.dumps(message["To"])
                url = re.search(r"http://nginx/public/v1/invoices/[A-Za-z0-9_-]+", message["Text"]).group()
                token = url.rsplit("/", 1)[1]
                response = http.get(url)
                assert response.status_code == 200
                assert response.headers["Cache-Control"] == "no-store"
                assert response.headers["Referrer-Policy"] == "no-referrer"
                invoice = response.json()
                assert invoice["invoice_code"] == payload["data"]["invoice_code"]
                assert invoice["total_amount"] == invoice["items"][0]["amount"] == 1500000
                assert "tenant_email_snapshot" not in invoice and "contract_id" not in invoice
                assert http.get("http://nginx/api/v1/invoices").status_code == 401
                assert http.post(f"http://nginx/internal/v1/invoices/{invoice_id}/access-links").status_code == 404

                with billing_db.begin() as db:
                    hashes = db.scalars(text("""
                        SELECT token_hash FROM invoice_access_tokens WHERE invoice_id=:id
                    """), {"id": invoice_id}).all()
                    assert hashes and all(len(value) == 64 and token not in value for value in hashes)
                    db.execute(text("""
                        UPDATE invoice_access_tokens SET expires_at = now() - interval '1 second'
                        WHERE invoice_id=:id
                    """), {"id": invoice_id})
                expired = http.get(url)
                assert expired.status_code == 404
                assert expired.headers["Cache-Control"] == "no-store"
    finally:
        billing_db.dispose()

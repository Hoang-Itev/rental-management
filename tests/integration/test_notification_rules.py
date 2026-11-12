"""P12 rules across disposable Billing, Tenant, Notification and RabbitMQ."""
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

if os.getenv("P12_EPHEMERAL_TEST") != "1":
    pytest.skip("P12 requires disposable databases", allow_module_level=True)

import aio_pika
import httpx
from sqlalchemy import create_engine, select, text

from app.clients import BillingClient, SmtpClient, TenantClient
from app.config import get_settings
from app.db import get_sessionmaker
from app.messaging import handle_delivery
from app.models import EmailJob
from app.service import send_next


def enqueue_from_service(service, database_url, function, now):
    statement = (
        "from datetime import datetime; from app.db import get_sessionmaker; "
        f"from {function[0]} import {function[1]}; "
        f"{function[1]}(get_sessionmaker(), datetime.fromisoformat({now.isoformat()!r}))"
    )
    subprocess.run(
        [sys.executable, "-c", statement], cwd=f"/p12/{service}", check=True,
        env={**os.environ, "PYTHONPATH": f"/p12/{service}", "DATABASE_URL": database_url},
    )


def seed_invoices(engine, today):
    invoices = {name: uuid4() for name in ("outstanding", "void_late", "paid_late", "already_paid", "due_today")}
    with engine.begin() as db:
        for name, invoice_id in invoices.items():
            db.execute(text("""
                INSERT INTO invoices (id, invoice_code, contract_id, room_id, invoice_type,
                                      billing_month, period_start, period_end, status, total_amount,
                                      due_date, issued_at, paid_at, tenant_name_snapshot,
                                      tenant_email_snapshot, room_code_snapshot)
                VALUES (:id, :code, :contract, :room, 'PERIODIC', '2024-11-01',
                        '2024-11-01', '2024-12-01', :status, 1500000, :due, now(),
                        :paid_at,
                        'Người thuê', 'tenant@example.com', 'A101')
            """), {"id": invoice_id, "code": name, "contract": uuid4(), "room": uuid4(),
                   "status": "PAID" if name == "already_paid" else "ISSUED",
                   "paid_at": datetime.now(timezone.utc) if name == "already_paid" else None,
                   "due": today if name == "due_today" else today - timedelta(days=1)})
    return invoices


def seed_contract(engine, today):
    contract_id, tenant_id = uuid4(), uuid4()
    with engine.begin() as db:
        db.execute(text("INSERT INTO tenants (id, full_name) VALUES (:id, 'Người thuê A102')"), {"id": tenant_id})
        db.execute(text("""
            INSERT INTO contracts (id, contract_code, room_id, room_code_snapshot,
                                   representative_tenant_id, start_date, end_date, status)
            VALUES (:id, :code, :room, 'A102', :tenant, :start, :end, 'ACTIVE')
        """), {"id": contract_id, "code": str(contract_id), "room": uuid4(), "tenant": tenant_id,
               "start": today - timedelta(days=30), "end": today + timedelta(days=7)})
    return contract_id


async def deliver_events(sessions, settings, expected):
    connection = await aio_pika.connect(os.environ["RABBITMQ_URL"], timeout=8)
    async with connection:
        channel = await connection.channel(on_return_raises=True)
        queue = await channel.get_queue("notification.events.q")
        exchange = await channel.get_exchange("rental.domain.v1")

        async def consume_one():
            for _ in range(150):
                message = await queue.get(fail=False, timeout=4)
                if message:
                    body = message.body
                    routing_key = message.routing_key
                    await handle_delivery(message, sessions, settings.owner_email)
                    return routing_key, body
                await asyncio.sleep(0.2)
            pytest.fail("Timed out waiting for Notification events")

        received = [await consume_one() for _ in range(expected)]
        for routing_key, body in received:
            await exchange.publish(aio_pika.Message(body), routing_key=routing_key, mandatory=True)
        for _ in received:
            await consume_one()
    return [json.loads(body) for _, body in received]


async def publish_events(events):
    connection = await aio_pika.connect(os.environ["RABBITMQ_URL"], timeout=8)
    async with connection:
        channel = await connection.channel(on_return_raises=True)
        exchange = await channel.get_exchange("rental.domain.v1")
        for key, payload in events:
            await exchange.publish(aio_pika.Message(json.dumps(payload).encode()), routing_key=key, mandatory=True)


def envelope(kind, aggregate_id, data):
    event_id = str(uuid4())
    return {"event_id": event_id, "correlation_id": event_id, "event_type": kind,
            "event_version": 1, "occurred_at": datetime.now(timezone.utc).isoformat(),
            "aggregate_id": str(aggregate_id), "data": data}


def test_reminder_rules_and_owner_mail():
    billing_url, tenant_url = os.environ["P12_BILLING_DATABASE_URL"], os.environ["P12_TENANT_DATABASE_URL"]
    billing_db, tenant_db = create_engine(billing_url), create_engine(tenant_url)
    sessions = get_sessionmaker()
    settings = get_settings()
    now = (datetime.now(timezone(timedelta(hours=7))) - timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0,
    )
    today = now.date()
    try:
        invoices = seed_invoices(billing_db, today)
        contract_id = seed_contract(tenant_db, today)
        renewed_id = seed_contract(tenant_db, today)
        for _ in range(2):
            enqueue_from_service("billing", billing_url, ("app.reminders", "enqueue_daily_reminders"), now)
            enqueue_from_service("tenant", tenant_url, ("app.scheduler", "enqueue_expiring_contracts"), now)
        with billing_db.begin() as db:
            db.execute(text("UPDATE invoices SET status='VOID', voided_at=now(), void_reason='test' WHERE id=:id"),
                       {"id": invoices["void_late"]})
            db.execute(text("UPDATE invoices SET status='PAID', paid_at=now() WHERE id=:id"),
                       {"id": invoices["paid_late"]})

        with tenant_db.begin() as db:
            db.execute(text("UPDATE contracts SET end_date = end_date + 30 WHERE id=:id"),
                       {"id": renewed_id})

        received = asyncio.run(deliver_events(sessions, settings, expected=5))
        assert {event["aggregate_id"] for event in received} == {
            *(str(invoices[name]) for name in ("outstanding", "void_late", "paid_late")), str(contract_id), str(renewed_id),
        }

        def status(invoice_id):
            with sessions() as db:
                return db.scalars(select(EmailJob).where(EmailJob.invoice_id == invoice_id)).one()

        def unavailable(request):
            raise httpx.ConnectError("Billing test outage", request=request)

        smtp = SmtpClient(settings)
        with httpx.Client(transport=httpx.MockTransport(unavailable)) as http, \
                httpx.Client(timeout=8, trust_env=False) as tenant_http:
            billing = BillingClient(http, settings)
            # Each of the three reminders checks Billing and defers, while owner mail sends.
            now_retry = datetime.now(timezone.utc)
            tenant = TenantClient(tenant_http, settings)
            for _ in range(5):
                assert send_next(sessions, billing, smtp, settings, tenant=tenant, clock=lambda: now_retry + timedelta(seconds=1))
        for name in ("outstanding", "void_late", "paid_late"):
            job = status(invoices[name])
            assert job.status == "PENDING" and job.attempt_count == 1 and job.next_attempt_at
            assert job.last_error == "Billing reminder eligibility unavailable"
        with sessions.begin() as db:
            db.execute(text("UPDATE email_jobs SET next_attempt_at=now() WHERE status='PENDING'"))

        with httpx.Client(timeout=8, trust_env=False) as http:
            billing = BillingClient(http, settings)
            tenant = TenantClient(http, settings)
            assert all(send_next(sessions, billing, smtp, settings, tenant=tenant) for _ in range(3))
            assert not send_next(sessions, billing, smtp, settings, tenant=tenant)
            assert status(invoices["paid_late"]).last_error == "ALREADY_PAID"
            assert status(invoices["void_late"]).last_error == "VOID"
            assert status(invoices["outstanding"]).status == "SENT"
            mailbox = http.get("http://mailpit:8025/api/v1/messages").raise_for_status().json()
            assert mailbox["total"] == 2
            subjects = {message["Subject"] for message in mailbox["messages"]}
            assert subjects == {"Nhắc thanh toán outstanding", "Hợp đồng phòng A102 sắp hết hạn"}
            owner_mail = next(item for item in mailbox["messages"] if "A102" in item["Subject"])
            assert settings.owner_email in json.dumps(owner_mail["To"])
        with sessions() as db:
            jobs = db.scalars(select(EmailJob)).all()
            assert len(jobs) == 5
            renewed = next(job for job in jobs if job.template_data.get("contract_id") == str(renewed_id))
            assert renewed.last_error == "CONTRACT_NO_LONGER_EXPIRING"
            assert sum(job.status == "SKIPPED" for job in jobs) == 3

        # Exercise both event orders on the shared Notification queue.
        invoice_id = invoices["outstanding"]
        original = next(event["data"] for event in received if event["aggregate_id"] == str(invoice_id))
        before = envelope("InvoiceReminderRequested", invoice_id, original)
        after = envelope("InvoiceReminderRequested", invoice_id, original)
        paid = envelope("PaymentSucceeded", invoice_id, {
            **original, "payment_attempt_id": str(uuid4()), "provider_transaction_id": "P12-123",
            "paid_amount": original["total_amount"], "paid_at": datetime.now(timezone.utc).isoformat(),
        })
        asyncio.run(publish_events([
            ("invoice.reminder_requested.v1", before),
            ("payment.succeeded.v1", paid),
            ("invoice.reminder_requested.v1", after),
        ]))
        asyncio.run(deliver_events(sessions, settings, expected=3))
        with sessions() as db:
            jobs = {str(job.source_event_id): job for job in db.scalars(select(EmailJob))}
            for event in (before, after):
                assert jobs[event["event_id"]].status == "SKIPPED"
            assert jobs[paid["event_id"]].status == "PENDING"
            assert len(jobs) == 8
        with httpx.Client(timeout=8, trust_env=False) as http:
            billing = BillingClient(http, settings)
            tenant = TenantClient(http, settings)
            assert send_next(sessions, billing, smtp, settings, tenant=tenant)
            assert not send_next(sessions, billing, smtp, settings, tenant=tenant)
            mailbox = http.get("http://mailpit:8025/api/v1/messages").raise_for_status().json()
            assert mailbox["total"] == 3
            assert sum(message["Subject"] == "Biên nhận outstanding" for message in mailbox["messages"]) == 1
    finally:
        billing_db.dispose()
        tenant_db.dispose()

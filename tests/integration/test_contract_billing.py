"""Run only against the disposable P09 databases."""
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

if os.getenv("P09_EPHEMERAL_TEST") != "1":
    pytest.skip("P09 requires disposable databases", allow_module_level=True)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from app.api import get_invoice_service
from app.db import get_engine, get_sessionmaker
from app.main import app
from app.messaging import RabbitPublisher, publish_pending
from app.models import Invoice, InvoiceAccessToken, OutboxEvent, PaymentAttempt
from app.scheduler import tick
from app.service import VN


@pytest.fixture
def seed():
    tenant_db = create_engine(os.environ["P09_TENANT_DATABASE_URL"])
    meter_db = create_engine(os.environ["P09_METERING_DATABASE_URL"])
    room, contract, payer = uuid4(), uuid4(), uuid4()
    meter_ids = {kind: uuid4() for kind in ("ELECTRICITY", "WATER")}
    with tenant_db.begin() as db:
        db.execute(text("INSERT INTO tenants (id, full_name, email) VALUES (:id, 'P09 Payer', 'p09@example.com')"),
                   {"id": payer})
        db.execute(text("""
            INSERT INTO contracts (id, contract_code, room_id, room_code_snapshot, representative_tenant_id,
                                   start_date, end_date, actual_end_date, status)
            VALUES (:id, :code, :room, 'P09-A1', :payer, '2024-11-16', '2025-02-01', '2024-11-30', 'ENDED')
        """), {"id": contract, "code": str(contract), "room": room, "payer": payer})
        db.execute(text("""
            INSERT INTO contract_terms (contract_id, effective_from, monthly_rent, electricity_unit_price,
                                        water_unit_price, monthly_service_fee)
            VALUES (:id, '2024-11-16', 3000000, 3500, 15000, 120000)
        """), {"id": contract})
    with meter_db.begin() as db:
        for kind, unit in (("ELECTRICITY", "KWH"), ("WATER", "M3")):
            meter = meter_ids[kind]
            db.execute(text("""
                INSERT INTO meters (id, room_id, meter_code, meter_type, unit)
                VALUES (:id, :room, :code, :kind, :unit)
            """), {"id": meter, "room": room, "code": str(meter), "kind": kind, "unit": unit})
            db.execute(text("""
                INSERT INTO meter_cutoffs (meter_id, contract_id, cutoff_type, cutoff_at, reading_value,
                                           source, status, confirmed_at)
                VALUES (:meter, :contract, 'CONTRACT_START', '2024-11-16 00:00+07', 100,
                        'AUTOMATIC', 'CONFIRMED', now())
            """), {"meter": meter, "contract": contract})
    yield contract, meter_db, meter_ids
    tenant_db.dispose()
    meter_db.dispose()


def test_monthly_job_waits_issues_atomically_and_deduplicates(seed):
    contract, meter_db, meters = seed
    path = "/api/v1/billing-runs"
    body = {"billing_month": "2024-11-01"}
    key = {"Idempotency-Key": str(uuid4())}
    with TestClient(app) as http, contextmanager(get_invoice_service)() as service:
        first = http.post(path, json=body, headers=key)
        assert first.status_code == 202, first.text
        run_id = first.json()["id"]
        assert first.json()["status"] == "RUNNING"
        assert http.post(path, json=body, headers=key).json()["id"] == run_id
        assert http.post(path, json={"billing_month": "2024-10-01"}, headers=key).status_code == 409
        tick(get_engine(), service, datetime.now(VN))
        run = next(row for row in http.get(path).json()["items"] if row["id"] == run_id)
        assert run["status"] == "COMPLETED" and run["waiting_count"] >= 1
        rows = http.get("/api/v1/invoices", params={"contract_id": contract, "status": "DRAFT"}).json()["items"]
        assert len(rows) == 1
        draft = rows[0]
        assert draft["blocked_reason"] == "PENDING_CUTOFF"
        url = "/api/v1/invoices/" + draft["id"]
        assert http.post(url + "/issue").status_code == 422
        assert http.get(url).json()["items"] == []
        with meter_db.begin() as db:
            for kind, end in (("ELECTRICITY", 120), ("WATER", 103)):
                db.execute(text("""
                    INSERT INTO meter_cutoffs (meter_id, cutoff_type, cutoff_at, reading_value,
                                               source, status, confirmed_at)
                    VALUES (:meter, 'MONTHLY', '2024-12-01 00:00+07', :reading,
                            'AUTOMATIC', 'CONFIRMED', now())
                """), {"meter": meters[kind], "reading": end})

        def break_outbox(session, *_):
            if any(isinstance(row, OutboxEvent) for row in session.new):
                raise RuntimeError("simulated outbox write failure")

        event.listen(Session, "before_flush", break_outbox)
        try:
            with pytest.raises(RuntimeError, match="outbox write"):
                service.process(contract, date(2024, 11, 1))
        finally:
            event.remove(Session, "before_flush", break_outbox)
        assert http.get(url).json()["status"] == "DRAFT"
        assert http.get(url).json()["items"] == []

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: http.post(url + "/issue"), range(2)))
        assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
        issued = responses[0].json()
        assert issued["status"] == "ISSUED"
        assert (issued["period_start"], issued["period_end"]) == ("2024-11-16", "2024-12-01")
        amounts = {item["item_type"]: item["amount"] for item in issued["items"]}
        assert amounts == {"RENT": 1500000, "SERVICE": 60000, "ELECTRICITY": 70000, "WATER": 45000}
        assert issued["total_amount"] == sum(amounts.values()) == 1675000

        rerun_id = http.post(path, json=body).json()["id"]
        tick(get_engine(), service, datetime.now(VN))
        rerun = next(row for row in http.get(path).json()["items"] if row["id"] == rerun_id)
        assert rerun["status"] == "COMPLETED" and rerun["skipped_count"] >= 1
        with get_sessionmaker()() as db:
            assert len(db.scalars(select(Invoice).where(Invoice.contract_id == contract)).all()) == 1
            outbox = db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id == issued["id"])).one()
            assert outbox.payload["data"]["total_amount"] == 1675000
            assert outbox.payload["data"]["period_end_exclusive"] == "2024-12-01"
            assert outbox.payload["data"]["recipient_email"] == "p09@example.com"
            assert outbox.published_at is None


    class UnavailableBroker:
        async def publish(self, body):
            raise ConnectionError("simulated disconnect")

    assert asyncio.run(publish_pending(get_sessionmaker(), UnavailableBroker(), limit=1)) == (0, True)
    with get_sessionmaker()() as db:
        row = db.get(OutboxEvent, outbox.id)
        assert row.published_at is None and row.attempts == 1

    if os.getenv("P09_RABBITMQ_TEST") == "1":
        asyncio.run(verify_broker(outbox.id, outbox.payload))


async def verify_broker(event_id, payload):
    import aio_pika

    connection = await aio_pika.connect(os.environ["RABBITMQ_URL"], timeout=10)
    async with connection:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        publisher = RabbitPublisher(channel)
        await publisher.start()
        assert await publish_pending(get_sessionmaker(), publisher) == (1, False)
        queue = await channel.get_queue("notification.events.q")
        message = await queue.get(timeout=5)
        async with message.process():
            assert message.message_id == str(event_id)
            assert json.loads(message.body) == payload
    with get_sessionmaker()() as db:
        assert db.get(OutboxEvent, event_id).published_at is not None


def test_final_bills_uncovered_period_then_reissue_preserves_history(seed):
    contract, meter_db, meters = seed
    tenant_db = create_engine(os.environ["P09_TENANT_DATABASE_URL"])
    with tenant_db.begin() as db:
        room = db.scalar(text("SELECT room_id FROM contracts WHERE id=:id"), {"id": contract})
        db.execute(text("UPDATE contracts SET start_date='2024-10-16' WHERE id=:id"), {"id": contract})
        db.execute(text("UPDATE contract_terms SET effective_from='2024-10-16' WHERE contract_id=:id"),
                   {"id": contract})

    previous_id = uuid4()
    now = datetime.now(timezone.utc)
    with get_sessionmaker().begin() as db:
        db.add(Invoice(
            id=previous_id, invoice_code=f"P13-OCT-{previous_id.hex}", contract_id=contract, room_id=room,
            invoice_type="PERIODIC", billing_month=date(2024, 10, 1), status="PAID", total_amount=1000000,
            period_start=date(2024, 10, 16), period_end=date(2024, 11, 1), due_date=date(2024, 11, 5),
            issued_at=now, paid_at=now, tenant_name_snapshot="P09 Payer",
            tenant_email_snapshot="p09@example.com", room_code_snapshot="P09-A1",
        ))

    with TestClient(app) as http, contextmanager(get_invoice_service)() as service:
        create = "/api/v1/final-invoices"
        response = http.post(create, json={"contract_id": str(contract)})
        assert response.status_code == 201, response.text
        draft = response.json()
        assert draft["invoice_type"] == "FINAL" and draft["status"] == "DRAFT"
        assert draft["blocked_reason"] == "PENDING_CUTOFF"
        assert (draft["period_start"], draft["period_end"]) == ("2024-11-01", "2024-12-01")
        assert http.post(create, json={"contract_id": str(contract)}).json()["id"] == draft["id"]
        assert service.process(contract, date(2024, 11, 1)) == ("skipped", None)

        def add_boundary(day, values):
            with meter_db.begin() as db:
                for meter, reading in zip(meters.values(), values):
                    db.execute(text("""
                        INSERT INTO meter_cutoffs (meter_id, cutoff_type, cutoff_at, reading_value,
                                                   source, status, confirmed_at)
                        VALUES (:meter, 'MONTHLY', :cutoff, :reading, 'AUTOMATIC', 'CONFIRMED', now())
                    """), {"meter": meter, "cutoff": datetime.combine(day, datetime.min.time(), tzinfo=VN),
                           "reading": reading})

        add_boundary(date(2024, 11, 1), (100, 100))
        add_boundary(date(2024, 12, 1), (120, 103))
        original_url = "/api/v1/invoices/" + draft["id"]
        issued_response = http.post(original_url + "/issue")
        assert issued_response.status_code == 200, issued_response.text
        issued = issued_response.json()
        assert issued["status"] == "ISSUED"
        assert issued["total_amount"] == 3235000
        assert http.post(original_url + "/adjustments", json={"reason": "Test", "amount_delta": 1}).status_code == 409

        with get_sessionmaker()() as db:
            event_id = db.scalar(select(OutboxEvent.id).where(OutboxEvent.aggregate_id == UUID(draft["id"])))
        link_response = http.post(f"/internal/v1/invoices/{draft['id']}/access-links",
                                  headers={"X-Service-Token": os.environ["SERVICE_TOKEN"]},
                                  json={"source_event_id": str(event_id), "recipient_email": "p09@example.com"})
        assert link_response.status_code == 201, link_response.text
        old_link = link_response.json()["url"]
        assert http.get(old_link).status_code == 200

        attempt_id = uuid4()
        with get_sessionmaker().begin() as db:
            db.add(PaymentAttempt(id=attempt_id, invoice_id=UUID(draft["id"]), provider="MOMO", amount=issued["total_amount"],
                                  order_id=attempt_id.hex, request_id=attempt_id.hex, status="PENDING"))
        reason = {"reason": "Corrected tariff"}
        assert http.post(original_url + "/void", json=reason).status_code == 409
        assert http.post(original_url + "/reissue", json=reason).status_code == 409
        with get_sessionmaker().begin() as db:
            db.get(PaymentAttempt, attempt_id).status = "FAILED"

        # A failed recalculation must keep the original invoice and access link usable.
        with meter_db.begin() as db:
            db.execute(text("UPDATE meter_cutoffs SET status='PENDING' WHERE meter_id=:id AND cutoff_type='MONTHLY'"),
                       {"id": meters["ELECTRICITY"]})
        assert http.post(original_url + "/reissue", json=reason).status_code == 422
        assert http.get(old_link).status_code == 200
        with meter_db.begin() as db:
            db.execute(text("UPDATE meter_cutoffs SET status='CONFIRMED' WHERE meter_id=:id AND cutoff_type='MONTHLY'"),
                       {"id": meters["ELECTRICITY"]})
        with tenant_db.begin() as db:
            db.execute(text("UPDATE contract_terms SET monthly_rent=3100000 WHERE contract_id=:id"), {"id": contract})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: http.post(original_url + "/reissue", json=reason), range(2)))
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        replacement = responses[0].json()
        assert responses[1].json()["id"] == replacement["id"]
        assert replacement["replaces_invoice_id"] == draft["id"] and replacement["revision"] == 2
        assert replacement["total_amount"] == 3335000
        old = http.get(original_url).json()
        assert old["status"] == "VOID" and old["void_reason"] == reason["reason"]
        assert old["total_amount"] == issued["total_amount"] and old["items"] == issued["items"]
        assert http.get(old_link).status_code == 404
        with get_sessionmaker()() as db:
            token = db.scalars(select(InvoiceAccessToken).where(InvoiceAccessToken.invoice_id == UUID(draft["id"]))).one()
            assert token.revoked_at is not None
            assert len(db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id == UUID(replacement["id"]))).all()) == 1

        paid_url = f"/api/v1/invoices/{previous_id}"
        assert http.post(paid_url + "/void", json=reason).status_code == 409
        assert http.post(paid_url + "/reissue", json=reason).status_code == 409
        adjustment = http.post(paid_url + "/adjustments", json={"reason": "Sai đơn giá", "amount_delta": -50000})
        assert adjustment.status_code == 201, adjustment.text
        resolve = f"/api/v1/invoice-adjustments/{adjustment.json()['id']}/resolve"
        resolution = {"status": "RESOLVED", "resolution_note": "Đã ghi nhận đối soát"}
        assert http.post(resolve, json=resolution).json()["status"] == "RESOLVED"
        assert http.post(resolve, json={"status": "REJECTED", "resolution_note": "Other"}).status_code == 409
        assert http.get(paid_url + "/adjustments").json()["items"][0]["amount_delta"] == -50000
        assert http.get(paid_url).json()["total_amount"] == 1000000
    tenant_db.dispose()

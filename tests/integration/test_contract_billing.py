"""Run only against the disposable P09 databases."""
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime
from uuid import uuid4

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
from app.models import Invoice, OutboxEvent
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

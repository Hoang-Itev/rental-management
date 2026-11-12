"""Actual Room HTTP -> Postgres Outbox -> RabbitMQ -> Metering, no mocks.

This test MUST run in a disposable Compose project with started room-outbox and
metering-consumer services. Never point it at live databases.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app import models as m
from app.db import get_engine

if os.getenv("P03_EPHEMERAL_TEST") != "1" or not os.getenv("P03_PROJECT_NAME", "").startswith(("p03test", "p03ci")):
    raise RuntimeError("Only execute P03 E2E in isolated randomized Compose project")

ROOM_BASE = "http://room:8000"
METER_BASE = "http://metering:8000"


def post(client: httpx.Client, route: str, data: dict) -> dict:
    r = client.post(ROOM_BASE + route, json=data)
    assert r.status_code == 201, (route, r.status_code, r.text)
    return r.json()


def wait_meters(client: httpx.Client, room_id: str, timeout: int = 50):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(METER_BASE + f"/internal/v1/rooms/{room_id}/meters",
                         headers={"X-Service-Token": os.environ["SERVICE_TOKEN"]})
        assert res.status_code == 200, res.text
        items = res.json()["items"]
        if len(items) == 2:
            return items
        time.sleep(0.5)
    raise AssertionError("RoomCreated not consumed: no pair of meters in 50s")


@pytest.mark.asyncio
async def test_real_roomcreated_queue_and_duplicate_deliveries():
    import aio_pika

    with httpx.Client(timeout=8) as client:
        prop = post(client, "/api/v1/properties", {"name": "P03 E2E " + str(uuid4()), "address": "ephemeral"})
        building = post(client, f"/api/v1/properties/{prop['id']}/buildings", {"name": "A"})
        floor = post(client, f"/api/v1/buildings/{building['id']}/floors", {"floor_number": 1})
        room = post(client, f"/api/v1/floors/{floor['id']}/rooms", {
            "room_code": "TEST01", "area_m2": "20.00", "listed_rent": 2000000,
        })
        room_id = room["id"]
        meters = wait_meters(client, room_id)
        public = client.get(METER_BASE + f"/api/v1/rooms/{room_id}/meters")
        assert public.status_code == 200, public.text
        assert public.json()['items'] == meters
        assert {(x["meter_type"], x["unit"]) for x in meters} == {
            ("ELECTRICITY", "KWH"), ("WATER", "M3")}

        room_db = create_engine(os.environ["ROOM_DATABASE_URL"], pool_pre_ping=True)
        try:
            deadline = time.monotonic() + 12
            while True:
                with room_db.connect() as conn:
                    row = conn.execute(text("""
                        SELECT payload, published_at FROM outbox_events
                        WHERE aggregate_id = :room_id AND event_type = 'RoomCreated'
                    """), {"room_id": UUID(room_id)}).one()
                if row.published_at is not None:
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError("Room outbox not marked published after broker confirm")
                time.sleep(0.25)
            payload = {k: v for k, v in row.payload.items() if k != "_batch"}
        finally:
            room_db.dispose()

        # A genuinely duplicated RabbitMQ delivery with the SAME event_id.
        connection = await aio_pika.connect_robust(os.environ["RABBITMQ_URL"])
        async with connection:
            ch = await connection.channel(publisher_confirms=True, on_return_raises=True)
            exchange = await ch.declare_exchange("rental.domain.v1", type=aio_pika.ExchangeType.TOPIC, durable=True)
            confirmation = await exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode(), content_type="application/json",
                                 delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key="room.created.v1", mandatory=True,
            )
            assert confirmation is not None and type(confirmation).__name__ == "Ack"

        # Allow the real consumer to ACK the duplicate, then assert uniqueness.
        time.sleep(2)
        assert {x["id"] for x in wait_meters(client, room_id)} == {x["id"] for x in meters}
        with Session(get_engine()) as db:
            assert db.scalar(select(func.count()).select_from(m.Meter).where(m.Meter.room_id == UUID(room_id))) == 2
            assert db.scalar(select(func.count()).select_from(m.ProcessedEvent).where(
                m.ProcessedEvent.event_id == UUID(payload["event_id"]))) == 1

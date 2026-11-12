"""Run BEFORE workers in isolated p03test/p03ci Compose project only."""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m, schemas as s
from app.db import get_engine, get_sessionmaker
from app.messaging import RabbitPublisher, publish_pending
from app.service import RoomService

if os.getenv("ROOM_P03_EPHEMERAL_TEST") != "1" or not os.getenv("P03_PROJECT_NAME", "").startswith(("p03test", "p03ci")):
    raise RuntimeError("Run P03 broker tests only against randomized disposable Compose project")


class BrokenBroker:
    async def publish(self, payload):
        raise OSError("simulated broker outage")


@pytest.mark.asyncio
async def test_outbox_retry_survives_broker_outage_and_confirms():
    engine = get_engine()
    sessions = get_sessionmaker()
    with sessions() as db:
        svc = RoomService(db)
        prop = svc.create_property(s.PropertyCreate(name="P03 broker test " + str(uuid4()), address="isolated"))
        b = svc.create_building(prop.id, s.BuildingCreate(name="A"))
        floor = svc.create_floor(b.id, s.FloorCreate(floor_number=1))
        room = svc.create_rooms(floor.id, s.RoomBulkCreate(rooms=[s.RoomCreateItem(
            room_code="T1", area_m2="19.00", listed_rent=1500000,
        )]))[0]
        db.commit()
        room_id = room.id

    with sessions() as db:
        event_id = db.scalar(select(m.OutboxEvent.id).where(m.OutboxEvent.aggregate_id == room_id))
        assert event_id is not None

    count, failed = await publish_pending(sessions, BrokenBroker(), limit=1)
    assert count == 0 and failed
    with sessions() as db:
        row = db.get(m.OutboxEvent, event_id)
        assert row.published_at is None and row.attempts == 1
        assert row.last_error.startswith("Publish failed")

    import aio_pika
    async with await aio_pika.connect_robust(os.environ["RABBITMQ_URL"]) as connection:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        sender = RabbitPublisher(channel)
        await sender.start()
        count, failed = await publish_pending(sessions, sender, limit=5)
        assert count == 1 and not failed

    with sessions() as db:
        row = db.get(m.OutboxEvent, event_id)
        assert row.published_at is not None and row.attempts == 2 and row.last_error is None

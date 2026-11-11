"""Fast checks for outbox state transitions. PostgreSQL locking is integration-tested."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app import messaging
from app import models as m


class StubSender:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def publish(self, body):
        if self.fail:
            raise ConnectionError("test only")
        self.sent.append(body)


@pytest.mark.asyncio
async def test_publish_confirm_marks_outbox(make_session, monkeypatch):
    row = m.OutboxEvent(id=uuid4(), aggregate_type="Room", aggregate_id=uuid4(),
                        event_type="RoomCreated", event_version=1,
                        payload={"event_id": str(uuid4()), "correlation_id": str(uuid4()), "_batch": {"private": True}},
                        attempts=0)
    with make_session() as db, db.begin():
        db.add(row)
    sender = StubSender()
    count, failed = await messaging.publish_pending(make_session, sender)
    assert count == 1 and not failed
    assert len(sender.sent) == 1 and "_batch" not in sender.sent[0]
    with make_session() as db:
        published = db.get(m.OutboxEvent, row.id)
        assert published.published_at is not None and published.attempts == 1
    count, failed = await messaging.publish_pending(make_session, sender)
    assert count == 0 and not failed and len(sender.sent) == 1


@pytest.mark.asyncio
async def test_publish_error_retains_pending_event(make_session):
    row = m.OutboxEvent(id=uuid4(), aggregate_type="Room", aggregate_id=uuid4(),
                        event_type="RoomCreated", event_version=1,
                        payload={"event_id": str(uuid4()), "correlation_id": str(uuid4())}, attempts=0)
    with make_session() as db, db.begin():
        db.add(row)
    count, failed = await messaging.publish_pending(make_session, StubSender(fail=True))
    assert count == 0 and failed
    with make_session() as db:
        pending = db.get(m.OutboxEvent, row.id)
        assert pending.published_at is None and pending.attempts == 1
    sender = StubSender()
    count, failed = await messaging.publish_pending(make_session, sender)
    assert count == 1 and not failed and len(sender.sent) == 1


@pytest.mark.asyncio
async def test_publish_rejects_invalid_limit(make_session):
    with pytest.raises(ValueError):
        await messaging.publish_pending(make_session, StubSender(), limit=0)

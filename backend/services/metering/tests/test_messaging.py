"""ACK, retry queue and DLQ paths without a broker process."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app import models as m
from app import messaging
from tests.support import example


class FakeMessage:
    def __init__(self, data, headers=None):
        self.body = json.dumps(data).encode() if not isinstance(data, bytes) else data
        self.headers = headers or {}
        self.actions = []
    async def ack(self): self.actions.append("ack")
    async def reject(self, requeue): self.actions.append("reject" if requeue else "reject-no-requeue")


@pytest.mark.asyncio
async def test_valid_and_duplicate_messages_ack_after_write(make_session):
    msg = FakeMessage(example())
    assert await messaging.process_delivery(msg, object(), make_session) == "processed"
    assert msg.actions == ["ack"]
    dup = FakeMessage(json.loads(msg.body))
    assert await messaging.process_delivery(dup, object(), make_session) == "duplicate"
    assert dup.actions == ["ack"]
    with make_session() as db:
        assert db.scalar(select(func.count()).select_from(m.Meter)) == 2


@pytest.mark.asyncio
async def test_invalid_message_transferred_then_ack(make_session, monkeypatch):
    transfers=[]
    async def copy(ch, q, body, headers):
        transfers.append(q)
    monkeypatch.setattr(messaging,"transfer",copy)
    bad=FakeMessage({"event_type": "unknown"})
    assert await messaging.process_delivery(bad,object(),make_session) == "deadletter"
    assert transfers == ["metering.events.q.dlq"] and bad.actions == ["ack"]


@pytest.mark.asyncio
async def test_transient_failure_retry_then_deadletter(make_session, monkeypatch):
    async def transfer(ch,q,body,headers):
        calls.append((q,headers["x-p03-retry"]))
    calls=[]
    monkeypatch.setattr(messaging,"transfer",transfer)
    from app import messaging as mod
    def fail(*args,**kwargs):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(mod.MeteringService,"process_room_created",fail)
    for retries, expected in [(0,"retry.10s"),(1,"retry.60s"),(2,"retry.300s"),(3,".dlq")]:
        m=FakeMessage(example(),headers={"x-p03-retry":retries})
        result=await mod.process_delivery(m,object(),make_session)
        assert result==("deadletter" if retries==3 else "retry")
        assert m.actions==["ack"]
        assert calls[-1][0]=="metering.events.q"+(expected if expected.startswith(".") else "."+expected)
        assert calls[-1][1]==retries+1


@pytest.mark.asyncio
async def test_retry_publish_failure_does_not_ack(make_session, monkeypatch):
    from app import messaging as mod
    def fail(*args,**kwargs):raise ConnectionError("temporary")
    async def fail_transfer(*args,**kwargs):raise ConnectionError("broker temporarily offline")
    monkeypatch.setattr(mod.MeteringService,"process_room_created",fail)
    monkeypatch.setattr(mod,"transfer",fail_transfer)
    msg=FakeMessage(example())
    with pytest.raises(ConnectionError):
        await mod.process_delivery(msg,object(),make_session)
    assert msg.actions == ["reject"]

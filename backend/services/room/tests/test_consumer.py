"""Room contract consumer: ACK/retry/DLQ/future safety."""
import json
from datetime import datetime,timezone
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from app import consumer


def envelope():
    cid=uuid4();room=uuid4()
    return {'event_id':str(uuid4()),'event_type':'ContractStarted','event_version':1,
            'aggregate_id':str(cid),'occurred_at':'2026-11-11T00:00:00+00:00',
            'effective_at':'2026-11-11T00:00:00+00:00',
            'correlation_id':str(uuid4()),'data':{'contract_id':str(cid),'room_id':str(room)}}


class Msg:
    def __init__(self,body,headers=None):
        self.body=json.dumps(body).encode() if not isinstance(body,bytes) else body
        self.headers=headers or {}
        self.ack=AsyncMock()
        self.reject=AsyncMock()


@pytest.mark.asyncio
async def test_success_manual_ack(monkeypatch,make_session):
    monkeypatch.setattr(consumer,'apply_contract_event',lambda db,data:'applied')
    msg=Msg(envelope())
    assert await consumer.delivery(msg,object(),make_session)=='applied'
    msg.ack.assert_awaited_once()
    msg.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_goes_dlq(monkeypatch,make_session):
    seen=[]
    async def transfer(*args):seen.append(args)
    monkeypatch.setattr(consumer,'transfer',transfer)
    msg=Msg(b'{invalid json')
    assert await consumer.delivery(msg,object(),make_session)=='deadletter'
    assert seen[0][1]=='room.events.q.dlq'
    msg.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_dlq_publish_failure_requeues(monkeypatch,make_session):
    async def fail(*args):raise OSError('broker unavailable')
    monkeypatch.setattr(consumer,'transfer',fail)
    msg=Msg({'bad':'event'})
    with pytest.raises(OSError):await consumer.delivery(msg,object(),make_session)
    msg.reject.assert_awaited_once_with(requeue=True)
    msg.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_future_is_deferred_without_poison_retry_count(monkeypatch,make_session):
    from app.lifecycle import FutureEvent
    def future(*args,**kwargs):raise FutureEvent('not due')
    monkeypatch.setattr(consumer,'apply_contract_event',future)
    seen=[]
    async def transfer(*args):seen.append(args)
    monkeypatch.setattr(consumer,'transfer',transfer)
    msg=Msg(envelope(),headers={'x-p05-retry':5})
    assert await consumer.delivery(msg,object(),make_session)=='deferred'
    assert seen[0][1]=='room.events.q.retry.300s'
    assert seen[0][3]['x-p05-retry']==5
    msg.ack.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('retry,dest',[(0,'room.events.q.retry.10s'),(3,'room.events.q.dlq')])
async def test_database_failure_retry_or_dlq(monkeypatch,make_session,retry,dest):
    def fail(*args,**kwargs):raise RuntimeError('db unavailable')
    monkeypatch.setattr(consumer,'apply_contract_event',fail)
    seen=[]
    async def transfer(*args):seen.append(args)
    monkeypatch.setattr(consumer,'transfer',transfer)
    msg=Msg(envelope(),headers={'x-p05-retry':retry})
    assert await consumer.delivery(msg,object(),make_session)=='retry'
    assert seen[0][1]==dest
    assert seen[0][3]['x-p05-retry']==retry+1


@pytest.mark.asyncio
async def test_database_failure_and_retry_transfer_failure_requeues(monkeypatch,make_session):
    def fail(*args,**kwargs):raise RuntimeError('db unavailable')
    async def bad(*args):raise OSError('lost broker')
    monkeypatch.setattr(consumer,'apply_contract_event',fail)
    monkeypatch.setattr(consumer,'transfer',bad)
    msg=Msg(envelope())
    with pytest.raises(OSError):await consumer.delivery(msg,object(),make_session)
    msg.reject.assert_awaited_once_with(requeue=True)

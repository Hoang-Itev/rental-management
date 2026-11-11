"""P06 AMQP manual ACK and TTL retry topic preservation tests."""
from __future__ import annotations
import json
from uuid import uuid4
import pytest
from app import messaging
from tests.test_service import new_meter, sample

class FakeMessage:
    def __init__(self, body, routing_key, headers=None):
        self.body = json.dumps(body).encode() if not isinstance(body, bytes) else body
        self.routing_key = routing_key
        self.headers = headers or {}
        self.actions = []
    async def ack(self): self.actions.append('ack')
    async def reject(self, requeue=False): self.actions.append('reject' if requeue else 'reject-drop')

@pytest.mark.asyncio
async def test_p06_delivery_ack_and_duplicate(make_session):
    with make_session() as db:
        meter = new_meter(db)
        db.commit()
    body = sample(meter.id)
    key = f'meters.{meter.id}.reading'
    first = FakeMessage(body, key)
    assert await messaging.process_telemetry_delivery(first, None, make_session) == 'inserted'
    assert first.actions == ['ack']
    second = FakeMessage(body, key)
    assert await messaging.process_telemetry_delivery(second, None, make_session) == 'duplicate'
    assert second.actions == ['ack']

@pytest.mark.asyncio
async def test_p06_malformed_and_mismatched_topic_to_dlq(make_session, monkeypatch):
    destinations=[]
    async def transfer(ch, dest, body, headers):destinations.append(dest)
    monkeypatch.setattr(messaging,'transfer',transfer)
    msg=FakeMessage({'meter_id':str(uuid4()),'measured_at':'2026-11-11T10:00:00Z','reading_value':2},
                    f'meters.{uuid4()}.reading')
    assert await messaging.process_telemetry_delivery(msg,None,make_session) == 'deadletter'
    assert msg.actions == ['ack']
    bad=FakeMessage(b'not json', 'meters.invalid.reading')
    assert await messaging.process_telemetry_delivery(bad,None,make_session) == 'deadletter'
    assert destinations == ['metering.telemetry.q.dlq'] * 2

@pytest.mark.asyncio
async def test_p06_retry_preserves_mqtt_origin_through_retry_queue(make_session, monkeypatch):
    with make_session() as db:
        meter = new_meter(db)
        db.commit()
    key=f'meters.{meter.id}.reading'
    transfers=[]
    async def transfer(ch,dest,body,headers):transfers.append((dest,headers))
    monkeypatch.setattr(messaging,'transfer',transfer)
    original=messaging.MeteringService.record_telemetry
    def fail(*a,**kw):raise ConnectionError('postgres unavailable')
    monkeypatch.setattr(messaging.MeteringService,'record_telemetry',fail)
    first=FakeMessage(sample(meter.id),key)
    assert await messaging.process_telemetry_delivery(first,None,make_session)=='retry'
    assert first.actions==['ack']
    assert transfers[0][0]=='metering.telemetry.q.retry.10s'
    assert transfers[0][1]['x-p06-original-key']==key
    monkeypatch.setattr(messaging.MeteringService,'record_telemetry',original)
    retried=FakeMessage(sample(meter.id),'metering.telemetry.q',transfers[0][1])
    assert await messaging.process_telemetry_delivery(retried,None,make_session)=='inserted'
    assert retried.actions==['ack']

@pytest.mark.asyncio
async def test_p06_transfer_failure_requeues_without_ack(make_session,monkeypatch):
    async def broken(*a,**kw):raise ConnectionError('Rabbit broker outage')
    monkeypatch.setattr(messaging,'transfer',broken)
    bad=FakeMessage(b'not json','bad.topic')
    with pytest.raises(ConnectionError):
        await messaging.process_telemetry_delivery(bad,None,make_session)
    assert bad.actions == ['reject']

"""P07 real RabbitMQ event + MQTT QoS1 + PostgreSQL cutoff flow.

Uses isolated randomized Compose project only. No direct write to other
services, no shared local database, no public HTTP ports.
"""
from __future__ import annotations
import asyncio
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import aio_pika
import httpx
import paho.mqtt.client as mqtt
from sqlalchemy import func, select
from app import models as m
from app.db import get_sessionmaker
from app.scheduler import run_due
from app.service import MeteringService

if os.getenv('P07_EPHEMERAL_TEST') != '1' or not os.getenv('P07_PROJECT_NAME', '').startswith(('p07test','p07ci')):
    raise RuntimeError('P07 E2E MUST run in an isolated disposable project')


def until(predicate, label, timeout=45):
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        with get_sessionmaker()() as db:
            value = predicate(db)
            if value:
                return value
        time.sleep(.3)
    raise AssertionError('Timed out: ' + label)


async def event_to_broker(key, envelope):
    conn = await aio_pika.connect_robust(os.environ['RABBITMQ_URL'], timeout=10)
    async with conn:
        channel = await conn.channel(publisher_confirms=True)
        exchange = await channel.get_exchange('rental.domain.v1')
        outcome = await exchange.publish(aio_pika.Message(
            body=json.dumps(envelope).encode('utf-8'),
            content_type='application/json',
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ), routing_key=key, mandatory=True)
        assert outcome is not None and type(outcome).__name__ == 'Ack'


def mqtt_snapshot(meters, measured_at):
    ready = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id='p07-flow-'+uuid4().hex[:12], protocol=mqtt.MQTTv311)
    client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ['MQTT_PASSWORD'])
    def connected(_client, _userdata, _flags, rc, _properties):
        if rc == 0:
            ready.set()
    client.on_connect = connected
    try:
        client.connect(os.environ.get('MQTT_HOST', 'rabbitmq'), int(os.environ.get('MQTT_PORT', '1883')), 40)
        client.loop_start()
        assert ready.wait(10), 'Real RabbitMQ MQTT broker unavailable'
        for meter in meters:
            payload = {'meter_id': str(meter.id), 'measured_at': measured_at.isoformat(),
                       'reading_value': '100.000' if meter.meter_type == 'ELECTRICITY' else '10.000'}
            info = client.publish('meters/'+str(meter.id)+'/reading', json.dumps(payload), qos=1)
            assert info.rc == 0
            info.wait_for_publish(timeout=10)
            assert info.is_published(), 'Missing MQTT QoS1 PUBACK'
    finally:
        client.disconnect()
        client.loop_stop()


def test_01_room_contract_mqtt_cutoff_manual_revision_and_idempotence():
    room, contract = uuid4(), uuid4()
    effective = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    room_event = {
        'event_id': str(uuid4()), 'event_type': 'RoomCreated', 'event_version': 1,
        'occurred_at': effective.isoformat(), 'correlation_id': str(uuid4()),
        'aggregate_id': str(room),
        'data': {'room_id': str(room), 'property_id': str(uuid4()),
                 'floor_id': str(uuid4()), 'room_code': 'P07-TEST'},
    }
    asyncio.run(event_to_broker('room.created.v1', room_event))
    meters = until(lambda db: list(db.scalars(select(m.Meter).where(m.Meter.room_id == room)))
                   if db.scalar(select(func.count()).select_from(m.Meter).where(m.Meter.room_id == room)) == 2
                   else None, 'RoomCreated -> 2 physical meters')
    assert {x.meter_type for x in meters} == {'ELECTRICITY','WATER'}

    contract_event = {
        'event_id': str(uuid4()), 'event_type': 'ContractStarted', 'event_version': 1,
        'occurred_at': effective.isoformat(), 'effective_at': effective.isoformat(),
        'correlation_id': str(uuid4()), 'aggregate_id': str(contract),
        'data': {'contract_id': str(contract), 'room_id': str(room)},
    }
    asyncio.run(event_to_broker('contract.started.v1', contract_event))
    cutoffs = until(lambda db: list(db.scalars(select(m.MeterCutoff).where(
        m.MeterCutoff.meter_id.in_([x.id for x in meters]))))
        if db.scalar(select(func.count()).select_from(m.MeterCutoff).where(
            m.MeterCutoff.meter_id.in_([x.id for x in meters]))) == 2 else None,
        'ContractStarted -> 2 pending cutoffs')
    assert all(c.status == 'PENDING' for c in cutoffs)

    # Real MQTT QoS1 samples are inside the 15-minute window.
    mqtt_snapshot(meters, effective + timedelta(minutes=3))
    until(lambda db: db.scalar(select(func.count()).select_from(m.MeterReading).where(
        m.MeterReading.meter_id.in_([x.id for x in meters]),
        m.MeterReading.validation_status == 'VALID')) == 2,
        'MQTT QoS1 -> 2 VALID PostgreSQL samples')

    first = run_due(now=datetime.now(timezone.utc))
    second = run_due(now=datetime.now(timezone.utc))
    assert first['auto_confirmed'] == 2, first
    assert second['auto_confirmed'] == 0 and second['monthly_created'] == 0, second
    with get_sessionmaker()() as db:
        actual=list(db.scalars(select(m.MeterCutoff).where(
            m.MeterCutoff.meter_id.in_([x.id for x in meters]))))
        assert len(actual) == 2
        assert all(x.status == 'CONFIRMED' and x.source == 'AUTOMATIC' for x in actual)
        assert all(x.source_reading_at is not None for x in actual)
        electricity = next(x for x in actual if x.meter_id == next(z.id for z in meters if z.meter_type == 'ELECTRICITY'))
        svc=MeteringService(db)
        version=svc.revise_cutoff(electricity.id, reading_value='102',
            reason='Correction verified in P07 end-to-end test', actor_id=uuid4())
        assert version.status == 'CONFIRMED' and version.supersedes_id == electricity.id
        assert electricity.status == 'SUPERSEDED'
        assert {(x.contract_id,x.reason_type) for x in svc.cutoff_reasons(version.id)} == {
            (contract,'CONTRACT_START')}
        db.commit()
    with httpx.Client(base_url='http://metering:8000', timeout=6) as client:
        assert client.get('/internal/v1/rooms/'+str(room)+'/cutoffs').status_code == 403
        reply=client.get('/internal/v1/rooms/'+str(room)+'/cutoffs',
            headers={'X-Service-Token':os.environ['SERVICE_TOKEN']})
        assert reply.status_code == 200, reply.text
        assert reply.json()['meta']['total'] == 2
        assert all(item['status']=='CONFIRMED' for item in reply.json()['items'])


def test_02_out_of_window_stays_pending_and_offline_recovers():
    meter = None
    room = uuid4()
    with get_sessionmaker()() as db:
        from app import repository as repo
        with db.begin():
            repo.ensure_meter(db, room, 'WATER')
        meter=repo.meters_for_room(db,room)[0]
        cutoff=m.MeterCutoff(id=uuid4(), meter_id=meter.id, cutoff_type='MONTHLY',
            cutoff_at=datetime.now(timezone.utc) - timedelta(hours=2),
            source='AUTOMATIC', status='PENDING')
        db.add(cutoff)
        db.commit()
        meter_id, cutoff_id = meter.id, cutoff.id
    with get_sessionmaker()() as db:
        svc = MeteringService(db)
        assert svc.finalize_due_cutoffs(now=datetime.now(timezone.utc)) == 0
        assert svc.cutoff(cutoff_id).status == 'PENDING'
        row = db.get(m.Meter,meter_id)
        row.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    now = datetime.now(timezone.utc)
    found = run_due(now=now)
    assert found['offline_alerts_created'] >= 1
    with get_sessionmaker()() as db:
        from app import repository as repo
        assert repo.open_offline(db,meter_id) is not None
    # Received MQTT QoS1 is a heartbeat and resolves OFFLINE.
    mqtt_snapshot([meter], now.replace(microsecond=0))
    until(lambda db: db.scalar(select(func.count()).select_from(m.MeterAlert).where(
        m.MeterAlert.meter_id == meter_id, m.MeterAlert.alert_type == 'OFFLINE',
        m.MeterAlert.status == 'RESOLVED')) == 1, 'MQTT heartbeat resolves offline alert')

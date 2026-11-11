"""Real MQTT QoS1 -> RabbitMQ amq.topic -> Metering queue -> PostgreSQL.

Runs only inside randomized disposable P06 Compose project. Simulator --once
is executed BEFORE this test and must create readings for both seeded meters.
"""
from __future__ import annotations
import os
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select,func
from app.db import get_sessionmaker
from app import models as m,repository as repo

if os.getenv('P06_EPHEMERAL_TEST') != '1' or not os.getenv('P06_PROJECT_NAME','').startswith(('p06test','p06ci')):
    raise RuntimeError('Refusing P06 E2E test outside a disposable Compose project')

WAIT=45

def until(predicate, label):
    deadline=time.monotonic()+WAIT
    while time.monotonic()<deadline:
        with get_sessionmaker()() as db:
            outcome=predicate(db)
            if outcome:
                return outcome
        time.sleep(.4)
    raise AssertionError('Timeout waiting for '+label)

class PublishMQTT:
    def __enter__(self):
        import paho.mqtt.client as mqtt
        ready=threading.Event()
        self.client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
            client_id='p06-e2e-'+uuid4().hex[:12],protocol=mqtt.MQTTv311)
        self.client.username_pw_set(os.environ['MQTT_USERNAME'],os.environ['MQTT_PASSWORD'])
        def on_connect(c,u,f,rc,properties):
            if rc==0:ready.set()
        self.client.on_connect=on_connect
        self.client.connect(os.environ['MQTT_HOST'],int(os.environ.get('MQTT_PORT','1883')),45)
        self.client.loop_start()
        assert ready.wait(10),'Could not connect to REAL RabbitMQ MQTT plugin'
        return self
    def publish(self, meter_id, stamp, value, *, topic_meter=None):
        payload={'meter_id':str(meter_id),'measured_at':stamp.isoformat(),
                 'reading_value':str(value)}
        topic='meters/'+str(topic_meter or meter_id)+'/reading'
        info=self.client.publish(topic,json.dumps(payload),qos=1,retain=False)
        assert info.rc==0,'MQTT publish returned error'
        info.wait_for_publish(timeout=10)
        assert info.is_published(),'MQTT QoS1 PUBACK missing'
    def __exit__(self,*a):
        self.client.disconnect()
        self.client.loop_stop()


def test_01_simulator_listing_and_real_snapshot_persisted():
    token=os.environ['SERVICE_TOKEN']
    with httpx.Client(timeout=6) as http:
        bad=http.get('http://metering:8000/internal/v1/meters')
        assert bad.status_code==403
        resp=http.get('http://metering:8000/internal/v1/meters',
                      headers={'X-Service-Token':token})
        assert resp.status_code==200,resp.text
        items=resp.json()['items']
        assert len(items)==2 and {m['meter_type'] for m in items}=={'ELECTRICITY','WATER'}
        
        meter_ids = {
            item["meter_type"]: item["id"]
            for item in items
        }

    def check(db):
        rows = list(
            db.scalars(
                select(m.MeterReading)
                .where(
                    m.MeterReading.meter_id.in_(
                        meter_ids.values()
                    )
                )
                .order_by(m.MeterReading.measured_at)
            )
        )

        electricity = [
            row for row in rows
            if str(row.meter_id) == meter_ids["ELECTRICITY"]
        ]

        water = [
            row for row in rows
            if str(row.meter_id) == meter_ids["WATER"]
        ]

        if len(electricity) == 2 and len(water) == 1:
            return electricity, water[0]

        return None

    electricity, water = until(
        check,
        "Simulator readings for seeded meters"
    )

    historical, new = electricity

    assert historical.reading_value == Decimal("1000000.000")
    assert new.measured_at > historical.measured_at
    assert new.validation_status == "VALID"
    assert new.reading_value > historical.reading_value

    assert water.validation_status == "VALID"
    assert water.reading_value >= 0
    assert water.measured_at.tzinfo is not None



def test_02_real_mqtt_duplicate_conflict_and_out_of_order():
    room=uuid4()
    with get_sessionmaker()() as db:
        with db.begin(): repo.ensure_meter(db,room,'ELECTRICITY')
        meter_id=repo.meters_for_room(db,room)[0].id
    base=datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=3)
    def rows(db):
        return list(db.scalars(select(m.MeterReading).where(m.MeterReading.meter_id==meter_id)))
    def alerts(db):
        return list(db.scalars(select(m.MeterAlert).where(m.MeterAlert.meter_id==meter_id)))
    with PublishMQTT() as client:
        client.publish(meter_id,base,'100.000')
        until(lambda db: len(rows(db))==1,'initial MQTT sample')
        client.publish(meter_id,base,'100.000')
        client.publish(meter_id,base,'999.000')
        until(lambda db: len(alerts(db))==1,'CONFLICTING_DUPLICATE alert')
        # Arrival order: t+2h first, then t+1h. Both must be VALID.
        client.publish(meter_id,base+timedelta(hours=2),'120.000')
        until(lambda db: len(rows(db))==2,'late parent reading')
        client.publish(meter_id,base+timedelta(hours=1),'110.000')
        until(lambda db: len(rows(db))==3,'out-of-order earlier reading')
        client.publish(meter_id,base+timedelta(minutes=30),'130.000')
        until(lambda db: len(rows(db))==4,'suspect out-of-order reading')
        client.publish(meter_id,base,'999.000')
        # Give consumer time to process the duplicate conflict redelivery.
        time.sleep(.5)
    with get_sessionmaker()() as db:
        found=rows(db)
        assert len(found)==4
        first=next(r for r in found if r.measured_at==base)
        assert first.reading_value==Decimal('100.000')
        assert sum(r.validation_status=='VALID' for r in found)==3
        assert sum(r.validation_status=='SUSPECT' for r in found)==1
        alarms=alerts(db)
        assert sum(a.alert_type=='CONFLICTING_DUPLICATE' for a in alarms)==1
        assert sum(a.alert_type=='READING_DECREASE' for a in alarms)==1


def test_03_topic_payload_mismatch_is_not_ingested():
    room1,room2=uuid4(),uuid4()
    with get_sessionmaker()() as db:
        with db.begin():
            repo.ensure_meter(db,room1,'WATER')
            repo.ensure_meter(db,room2,'WATER')
        source=repo.meters_for_room(db,room1)[0].id
        wrong_topic=repo.meters_for_room(db,room2)[0].id
    when=datetime.now(timezone.utc).replace(microsecond=0)-timedelta(hours=1)
    with PublishMQTT() as client:
        client.publish(source,when,'5',topic_meter=wrong_topic)
    # Prove the malformed payload reached Metering and was quarantined;
    # a missing routing binding would otherwise make a DB-only check pass.
    import asyncio
    import aio_pika
    async def read_dead_letter():
        conn=await aio_pika.connect_robust(os.environ['RABBITMQ_URL'],timeout=8)
        async with conn:
            channel=await conn.channel()
            queue=await channel.declare_queue('metering.telemetry.q.dlq',durable=True)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                msg=await queue.get(fail=False)
                if msg is not None:
                    async with msg.process():
                        body=json.loads(msg.body)
                        assert body['meter_id']==str(source)
                    return
                await asyncio.sleep(.3)
        raise AssertionError('Topic-payload mismatch did not reach telemetry DLQ')
    asyncio.run(read_dead_letter())
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(m.MeterReading).where(
            m.MeterReading.meter_id==source))==0

"""True Room/Tenant/Metering PostgreSQL + RabbitMQ integration on disposable project.

Direct service-to-service HTTP is used: no JWT in this isolated worker integration.
The separate Gateway P05 check remains a manual owner acceptance step.
"""
from __future__ import annotations
import asyncio
import json
import os
import time
from datetime import date, datetime, time as daytime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select, func, text

PROJ=os.getenv('P05_PROJECT_NAME','')
if os.getenv('P05_EPHEMERAL_TEST')!='1' or not PROJ.startswith(('p05test','p05ci')):
    raise RuntimeError('P05 integration ONLY runs on a randomized disposable Compose project')
ROOM=os.getenv('ROOM_URL','http://room:8000').rstrip('/')
TENANT=os.getenv('P05_TENANT_URL','http://tenant:8000').rstrip('/')
METERING=os.getenv('METERING_URL','http://metering:8000').rstrip('/')
VN=timezone(timedelta(hours=7))


def api(method,base,path,body=None):
    with httpx.Client(timeout=12,trust_env=False) as c:
        return c.request(method,base+path,json=body)


def ok(method,base,path,body=None,status=200):
    r=api(method,base,path,body)
    assert r.status_code==status,(method,path,r.status_code,r.text[:700])
    return r.json()


def eventually(fn,limit=30):
    start=time.monotonic()
    last=None
    while time.monotonic()-start<limit:
        try:
            result=fn()
            if result:return result
        except (AssertionError,httpx.RequestError) as exc:last=exc
        time.sleep(.35)
    raise AssertionError('Timed out waiting for asynchronous business projection: '+str(last))


@pytest.fixture(scope='module')
def root():
    suffix=uuid4().hex[:8]
    p=ok('POST',ROOM,'/api/v1/properties',{'name':'P05 ephemeral '+suffix,'address':'Disposable'},201)
    b=ok('POST',ROOM,f"/api/v1/properties/{p['id']}/buildings",{'name':'A'},201)
    floor=ok('POST',ROOM,f"/api/v1/buildings/{b['id']}/floors",{'floor_number':1},201)
    def create_room(code):
        r=ok('POST',ROOM,f"/api/v1/floors/{floor['id']}/rooms",
             {'room_code':code,'area_m2':'21.00','listed_rent':2000000},201)
        eventually(lambda: len(get_meters(r['id']))==2)
        return r
    return create_room


def get_meters(room_id):
    with httpx.Client(timeout=5,trust_env=False) as client:
        r=client.get(f'{METERING}/internal/v1/rooms/{room_id}/meters',
                     headers={'X-Service-Token':os.environ['SERVICE_TOKEN']})
    assert r.status_code==200,r.text
    return r.json()['items']


def make_draft(room_id,payer,start,end):
    return ok('POST',TENANT,'/api/v1/contracts',{
        'contract_code':'P05-'+uuid4().hex[:12], 'room_id':room_id,
        'representative_tenant_id':payer, 'start_date':start.isoformat(),
        'end_date':end.isoformat(), 'initial_terms':{
            'effective_from':start.isoformat(),'monthly_rent':2000000,
            'electricity_unit_price':3500,'water_unit_price':17000}},201)


def job(as_of):
    return ok('POST',TENANT,'/api/v1/jobs/contracts/lifecycle/run',
              {'as_of':as_of.isoformat()},202)


def occupancy(room_id):
    return ok('GET',ROOM,f'/api/v1/rooms/{room_id}')['occupancy_contract_id']


def boundary(day):return datetime.combine(day,daytime.min,tzinfo=VN)


def test_real_lifecycle_and_handover(root):
    room=root('P05A1')
    payer=ok('POST',TENANT,'/api/v1/tenants',
             {'full_name':'P05 E2E Tenant','email':'p05-e2e@example.org'},201)
    today=datetime.now(VN).date()
    a_start=today-timedelta(days=2)
    a_end=today+timedelta(days=2)
    a=make_draft(room['id'],payer['id'],a_start,a_end)
    assert ok('POST',TENANT,f"/api/v1/contracts/{a['id']}/confirm")['status']=='SCHEDULED'
    job(datetime.now(timezone.utc))
    eventually(lambda: occupancy(room['id'])==a['id'])
    eventually(lambda: get_meters(room['id']) and cutoff_count(room['id'])>=2)
    assert ok('GET',TENANT,f"/api/v1/contracts/{a['id']}")['status']=='ACTIVE'

    # Owner records a handover yesterday (event is now due).
    ended=ok('POST',TENANT,f"/api/v1/contracts/{a['id']}/end",
             {'actual_end_date':(today-timedelta(days=1)).isoformat(),
              'reason':'Resident moved out'})
    assert ended['status']=='ENDED'
    eventually(lambda: occupancy(room['id']) is None)

    # New B starts on the same physical midnight as End(A).
    b=make_draft(room['id'],payer['id'],today,today+timedelta(days=20))
    ok('POST',TENANT,f"/api/v1/contracts/{b['id']}/confirm")
    job(datetime.now(timezone.utc))
    eventually(lambda: occupancy(room['id'])==b['id'])
    assert len(get_meters(room['id']))==2
    assert ok('GET',TENANT,f"/api/v1/contracts/{b['id']}")['status']=='ACTIVE'
    eventually(lambda: handover_reason_count(room['id'],a['id'],b['id'])==6)


def db():return create_engine(os.environ['METERING_DATABASE_URL'],pool_pre_ping=True)


def cutoff_count(room_id):
    engine=db()
    try:
        with engine.connect() as c:
            return c.execute(text('SELECT COUNT(*) FROM meter_cutoffs WHERE meter_id IN (SELECT id FROM meters WHERE room_id=:r)'),{'r':room_id}).scalar_one()
    finally:engine.dispose()


def handover_reason_count(room_id,a,b):
    engine=db()
    try:
        with engine.connect() as c:
            return c.execute(text('''SELECT COUNT(*) FROM meter_cutoff_reasons cr
               JOIN meter_cutoffs c ON c.id=cr.cutoff_id
               JOIN meters m ON m.id=c.meter_id
               WHERE m.room_id=:r AND cr.contract_id IN (:a,:b)'''),
               {'r':room_id,'a':a,'b':b}).scalar_one()
    finally:engine.dispose()


async def publish_events(events):
    import aio_pika
    conn=await aio_pika.connect_robust(os.environ['RABBITMQ_URL'])
    async with conn:
        ch=await conn.channel(publisher_confirms=True,on_return_raises=True)
        ex=await ch.declare_exchange('rental.domain.v1',type=aio_pika.ExchangeType.TOPIC,durable=True)
        for ev in events:
            rk='contract.started.v1' if ev['event_type']=='ContractStarted' else 'contract.ended.v1'
            msg=aio_pika.Message(body=json.dumps(ev).encode(),content_type='application/json',
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,message_id=ev['event_id'])
            await ex.publish(msg,routing_key=rk,mandatory=True)


def synthetic(kind,room,contract,when):
    return {'event_id':str(uuid4()),'event_type':kind,'event_version':1,
            'occurred_at':datetime.now(timezone.utc).isoformat(),
            'effective_at':when.isoformat(),'correlation_id':str(uuid4()),
            'aggregate_id':str(contract),'data':{'room_id':room,'contract_id':str(contract)}}


@pytest.mark.parametrize('reverse',[False,True])
def test_both_arrival_orders_and_stale_events(root,reverse):
    room=root('P05B'+str(int(reverse)))
    today=datetime.now(VN).date()
    first=boundary(today-timedelta(days=2))
    handover=boundary(today-timedelta(days=1))
    a,b=uuid4(),uuid4()
    start_a=synthetic('ContractStarted',room['id'],a,first)
    end_a=synthetic('ContractEnded',room['id'],a,handover)
    start_b=synthetic('ContractStarted',room['id'],b,handover)
    asyncio.run(publish_events([start_a]))
    eventually(lambda: occupancy(room['id'])==str(a))
    asyncio.run(publish_events([start_b,end_a] if reverse else [end_a,start_b]))
    eventually(lambda: occupancy(room['id'])==str(b))
    eventually(lambda: handover_reason_count(room['id'],str(a),str(b))>=6)
    asyncio.run(publish_events([start_a,end_a,start_b]))
    time.sleep(.8)
    assert occupancy(room['id'])==str(b)
    assert len(get_meters(room['id']))==2
    assert cutoff_count(room['id'])==4

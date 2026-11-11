"""P04 REAL HTTP integration: Room REST + two independent PostgreSQL service DBs.

Run ONLY in a randomized disposable p04test/p04ci Docker Compose project.
Nginx/JWT is separately tested by optional scripts/test_p04_gateway.ps1.
"""
from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx
import pytest

PROJECT=os.getenv('P04_PROJECT_NAME','')
if os.getenv('P04_EPHEMERAL_TEST')!='1' or not PROJECT.startswith(('p04test','p04ci')):
    raise RuntimeError('P04 integration runs ONLY inside randomized disposable Compose project')

ROOM=os.environ.get('ROOM_URL','http://room:8000').rstrip('/')
TENANT=os.environ.get('P04_TENANT_URL','http://tenant:8000').rstrip('/')


def request(method, base, path, data=None):
    with httpx.Client(timeout=12,trust_env=False) as client:
        return client.request(method,base+path,json=data)

def checked(method,base,path,data=None,status=200):
    response=request(method,base,path,data)
    assert response.status_code==status,(method,path,response.status_code,response.text[:550])
    return response.json() if response.content else None

@pytest.fixture(scope='module')
def tree():
    suffix=uuid4().hex[:10]
    prop=checked('POST',ROOM,'/api/v1/properties',{'name':'P04 isolated '+suffix,'address':'Only temporary DB'},201)
    building=checked('POST',ROOM,f"/api/v1/properties/{prop['id']}/buildings",{'name':'A'},201)
    floor=checked('POST',ROOM,f"/api/v1/buildings/{building['id']}/floors",{'floor_number':1},201)
    def create_room(code):
        return checked('POST',ROOM,f"/api/v1/floors/{floor['id']}/rooms",
                       {'room_code':code,'area_m2':'25.00','listed_rent':2500000},201)
    return floor,create_room


def draft(room_id,tenant_id,start,end,code=None,first_end=None):
    return checked('POST',TENANT,'/api/v1/contracts',{
        'contract_code':code or 'P04-'+uuid4().hex[:12],
        'room_id':str(room_id),'representative_tenant_id':tenant_id,
        'start_date':start,'end_date':end,
        'initial_terms':{'effective_from':start,'effective_to':first_end,
                         'monthly_rent':2500000,'electricity_unit_price':3500,
                         'water_unit_price':18000,'monthly_service_fee':0}},201)


def test_room_tenant_confirmation_terms_and_postgres_exclusion(tree):
    floor,create_room=tree
    payer=checked('POST',TENANT,'/api/v1/tenants',{
        'full_name':'P04 Integration Tenant','email':'p04@example.com'},201)
    room=create_room('A101')
    first=draft(room['id'],payer['id'],'2026-12-01','2027-03-31',first_end='2027-01-01')
    second=checked('POST',TENANT,f"/api/v1/contracts/{first['id']}/terms",{
        'effective_from':'2027-01-01','monthly_rent':2700000,
        'electricity_unit_price':3500,'water_unit_price':18000},201)
    assert second['monthly_rent']==2700000
    versions=checked('GET',TENANT,f"/api/v1/contracts/{first['id']}/terms")
    assert len(versions['items'])==2 and versions['items'][0]['effective_to']=='2027-01-01'
    confirmed=checked('POST',TENANT,f"/api/v1/contracts/{first['id']}/confirm")
    assert confirmed['status']=='SCHEDULED'
    assert checked('POST',TENANT,f"/api/v1/contracts/{first['id']}/confirm")['status']=='SCHEDULED'
    history=checked('GET',TENANT,f"/api/v1/contracts/{first['id']}/events")
    assert [x['event_type'] for x in history['items']]==['CREATED','CONFIRMED']

    overlapping=draft(room['id'],payer['id'],'2027-03-31','2027-04-15')
    assert request('POST',TENANT,f"/api/v1/contracts/{overlapping['id']}/confirm").status_code==409
    assert checked('GET',TENANT,f"/api/v1/contracts/{overlapping['id']}")['status']=='DRAFT'
    adjacent=draft(room['id'],payer['id'],'2027-04-01','2027-06-30')
    assert checked('POST',TENANT,f"/api/v1/contracts/{adjacent['id']}/confirm")['status']=='SCHEDULED'


def test_inactive_room_and_term_date_validation(tree):
    floor,create_room=tree
    payer=checked('POST',TENANT,'/api/v1/tenants',{
        'full_name':'Second payer','email':'second@example.com'},201)
    room=create_room('A102')
    contract=draft(room['id'],payer['id'],'2027-01-01','2027-02-28',first_end='2027-01-15')
    checked('PATCH',ROOM,f"/api/v1/rooms/{room['id']}",{'status':'INACTIVE'})
    assert request('POST',TENANT,f"/api/v1/contracts/{contract['id']}/confirm").status_code==409
    assert checked('GET',TENANT,f"/api/v1/contracts/{contract['id']}")['status']=='DRAFT'
    assert request('POST',TENANT,'/api/v1/contracts',{
        'contract_code':'Invalid-'+uuid4().hex[:10],'room_id':room['id'],
        'representative_tenant_id':payer['id'],'start_date':'2027-05-20','end_date':'2027-05-10',
        'initial_terms':{'effective_from':'2027-05-20','monthly_rent':1,
                         'electricity_unit_price':1,'water_unit_price':1}}).status_code==422


def test_two_concurrent_confirmations_cannot_overlap(tree):
    floor,create_room=tree
    payer=checked('POST',TENANT,'/api/v1/tenants',{'full_name':'Concurrent','email':'conc@example.com'},201)
    room=create_room('A103')
    c1=draft(room['id'],payer['id'],'2027-08-01','2027-10-31')
    c2=draft(room['id'],payer['id'],'2027-09-01','2027-12-31')
    def confirm(cid): return request('POST',TENANT,f'/api/v1/contracts/{cid}/confirm').status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(confirm,c['id']) for c in (c1,c2)]
        statuses=[f.result(timeout=25) for f in futures]
    assert sorted(statuses)==[200,409],statuses
    states=[checked('GET',TENANT,f"/api/v1/contracts/{c['id']}")['status'] for c in (c1,c2)]
    assert sorted(states)==['DRAFT','SCHEDULED']
    # Defend against duplicate/no-op confirmation events.
    for c in (c1,c2):
        evs=checked('GET',TENANT,f"/api/v1/contracts/{c['id']}/events")['items']
        assert [e['event_type'] for e in evs].count('CONFIRMED')==(1 if checked('GET',TENANT,f"/api/v1/contracts/{c['id']}")['status']=='SCHEDULED' else 0)

from __future__ import annotations
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.config import get_settings,TenantSettings
from app import api,api_internal
from app.clients import RoomUnavailable
from app import schemas as s

@pytest.fixture
def client(sessions,room,monkeypatch):
    def db_override():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=db_override
    settings=TenantSettings(SERVICE_TOKEN='p'*32,ROOM_URL='http://room:8000')
    app.dependency_overrides[get_settings]=lambda:settings
    monkeypatch.setattr(api.RoomClient,'validate',lambda self,room_id:room.validate(room_id))
    with TestClient(app) as c:yield c
    app.dependency_overrides.clear()


def test_tenant_api_create_list_patch(client):
    r=client.post('/api/v1/tenants',json={'full_name':'  Student A  ','email':'a@example.com'})
    assert r.status_code==201 and r.json()['full_name']=='Student A'
    uid=r.json()['id']
    assert client.get('/api/v1/tenants').json()['meta']['total']==1
    assert client.get('/api/v1/tenants/'+uid).status_code==200
    assert client.patch('/api/v1/tenants/'+uid,json={'full_name':'New A'}).json()['full_name']=='New A'
    assert client.patch('/api/v1/tenants/'+uid,json={}).status_code==422
    assert client.post('/api/v1/tenants',json={'full_name':''}).status_code==422


def test_contract_full_http_flow(client,room):
    rid=uuid4();room.available[rid]=True
    uid=client.post('/api/v1/tenants',json={'full_name':'Client','email':'client@example.com'}).json()['id']
    data={'contract_code':'CT-1','room_id':str(rid),'representative_tenant_id':uid,
        'start_date':'2026-12-01','end_date':'2027-01-31',
        'initial_terms':{'effective_from':'2026-12-01','monthly_rent':2500000,
                         'electricity_unit_price':3000,'water_unit_price':17000}}
    draft=client.post('/api/v1/contracts',json=data,headers={'X-Auth-User-Id':str(uuid4())})
    assert draft.status_code==201,draft.text
    cid=draft.json()['id']
    assert draft.json()['status']=='DRAFT'
    assert client.get('/api/v1/contracts').json()['meta']['total']==1
    assert client.get('/api/v1/contracts/'+cid).status_code==200
    assert len(client.get('/api/v1/contracts/'+cid+'/terms').json()['items'])==1
    assert client.post('/api/v1/contracts/'+cid+'/terms',json={'effective_from':'2027-01-01',
       'monthly_rent':3000000,'electricity_unit_price':3000,'water_unit_price':18000}).status_code==201
    resp=client.post('/api/v1/contracts/'+cid+'/confirm')
    assert resp.status_code==200,resp.text
    assert resp.json()['status']=='SCHEDULED'
    assert [e['event_type'] for e in client.get('/api/v1/contracts/'+cid+'/events').json()['items']]==['CREATED','CONFIRMED']
    assert client.get('/api/v1/contracts?status=SCHEDULED').json()['meta']['total']==1
    assert client.patch('/api/v1/contracts/'+cid,json={'end_date':'2027-02-28'}).status_code==409
    assert client.post('/api/v1/contracts/'+cid+'/confirm').status_code==200
    assert client.post('/api/v1/contracts',json={**data,'contract_code':'CT-2'}).status_code==201
    assert client.get('/api/v1/contracts/'+str(uuid4())).status_code==404


def test_api_rejects_inactive_room_and_bad_payload(client,room):
    rid=uuid4();room.available[rid]=False
    uid=client.post('/api/v1/tenants',json={'full_name':'Client','email':'payer@example.com'}).json()['id']
    data={'contract_code':'CNT','room_id':str(rid),'representative_tenant_id':uid,
          'start_date':'2026-12-01','end_date':'2026-12-31',
          'initial_terms':{'effective_from':'2026-12-01','monthly_rent':1,'electricity_unit_price':1,'water_unit_price':1}}
    draft=client.post('/api/v1/contracts',json=data)
    assert draft.status_code==201
    res=client.post('/api/v1/contracts/'+draft.json()['id']+'/confirm')
    assert res.status_code==409 and res.json()['code']=='CONFLICT'
    assert client.post('/api/v1/contracts',json={**data,'contract_code':'INVALID','end_date':'2026-11-30'}).status_code==422
    assert client.get('/api/v1/tenants?page=0').status_code==422


def test_internal_auth_and_error_body(client,room):
    rid=uuid4();room.available[rid]=True
    uid=client.post('/api/v1/tenants',json={'full_name':'Client','email':'p@example.com'}).json()['id']
    data={'contract_code':'C3','room_id':str(rid),'representative_tenant_id':uid,
          'start_date':'2026-12-01','end_date':'2026-12-31',
          'initial_terms':{'effective_from':'2026-12-01','monthly_rent':1,'electricity_unit_price':1,'water_unit_price':1}}
    cid=client.post('/api/v1/contracts',json=data).json()['id']
    route='/internal/v1/contracts/'+cid
    assert client.get(route).status_code==403
    assert client.get(route,headers={'X-Service-Token':'bad'}).status_code==403
    good=client.get(route,headers={'X-Service-Token':'p'*32})
    assert good.status_code==200 and len(good.json()['terms'])==1
    assert good.json()['payer']['email']=='p@example.com'
    assert client.get('/internal/v1/contracts/'+str(uuid4()),headers={'X-Service-Token':'p'*32}).status_code==404

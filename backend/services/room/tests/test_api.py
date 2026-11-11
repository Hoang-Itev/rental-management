"""HTTP contract, validation, pagination and atomic bulk creation through TestClient."""
from uuid import uuid4

from sqlalchemy import func, select

from app import models as m


def setup_tree(c):
    p=c.post('/api/v1/properties',json={'name':'  Khu 1  ','address':'  1 abc  '})
    assert p.status_code==201, p.text
    pid=p.json()['id']
    b=c.post(f'/api/v1/properties/{pid}/buildings',json={'name':'Dãy A'})
    assert b.status_code==201, b.text
    bid=b.json()['id']
    f=c.post(f'/api/v1/buildings/{bid}/floors',json={'floor_number':1,'name':'Tầng 1'})
    assert f.status_code==201, f.text
    fid=f.json()['id']
    return pid,bid,fid


def new_room(code='A101',**extra):
    return {'room_code':code,'area_m2':'22.50','listed_rent':2500000,**extra}


def test_all_routes_create_read_patch_and_deactivate(client):
    pid,bid,fid=setup_tree(client)
    assert client.get('/api/v1/properties').json()['meta']['total']==1
    assert client.get(f'/api/v1/properties/{pid}').json()['name']=='Khu 1'
    assert client.patch(f'/api/v1/properties/{pid}',json={'name':'Khu 2'}).json()['name']=='Khu 2'
    assert client.get(f'/api/v1/properties/{pid}/buildings').json()['meta']['total']==1
    assert client.get(f'/api/v1/buildings/{bid}').json()['name']=='Dãy A'
    assert client.patch(f'/api/v1/buildings/{bid}',json={'name':'Dãy B'}).json()['name']=='Dãy B'
    assert client.get(f'/api/v1/buildings/{bid}/floors').json()['meta']['total']==1
    assert client.get(f'/api/v1/floors/{fid}').json()['floor_number']==1
    assert client.patch(f'/api/v1/floors/{fid}',json={'name':'Tầng cao'}).json()['name']=='Tầng cao'
    item=client.post(f'/api/v1/floors/{fid}/rooms',json=new_room('a101'))
    assert item.status_code==201, item.text
    room=item.json()
    assert room['room_code']=='A101' and room['display_occupancy']=='VACANT'
    assert room['area_m2']==22.5
    rid=room['id']
    assert client.get(f'/api/v1/rooms/{rid}').json()['id']==rid
    assert client.patch(f'/api/v1/rooms/{rid}',json={'listed_rent':3000000}).json()['listed_rent']==3000000
    assert client.get('/api/v1/rooms',params={'property_id':pid}).json()['meta']['total']==1
    assert client.delete(f'/api/v1/properties/{pid}').status_code==409
    assert client.delete(f'/api/v1/buildings/{bid}').status_code==409
    assert client.delete(f'/api/v1/floors/{fid}').status_code==409
    assert client.delete(f'/api/v1/rooms/{rid}').status_code==204
    assert client.delete(f'/api/v1/rooms/{rid}').status_code==204
    assert client.get(f'/api/v1/rooms/{rid}').json()['status']=='INACTIVE'
    assert client.delete(f'/api/v1/floors/{fid}').status_code==204
    assert client.delete(f'/api/v1/buildings/{bid}').status_code==204
    assert client.delete(f'/api/v1/properties/{pid}').status_code==204


def test_bulk_duplicate_entire_request_rejected_and_rollback(client,make_session):
    pid,bid,fid=setup_tree(client)
    resp=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room('A101'),new_room('a101')]})
    assert resp.status_code==422
    resp=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room('A101'),new_room('A102')]})
    assert resp.status_code==201 and len(resp.json())==2
    resp=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room('A103'),new_room('A101')]})
    assert resp.status_code==409
    assert resp.json()['code']=='CONFLICT'
    assert client.get('/api/v1/rooms').json()['meta']['total']==2
    with make_session() as db:
        assert db.scalar(select(func.count()).select_from(m.OutboxEvent))==2


def test_cross_property_and_missing_parent(client):
    pid,bid,fid=setup_tree(client)
    prop2=client.post('/api/v1/properties',json={'name':'Other','address':'2 abc'}).json()['id']
    bad=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room('A101',property_id=prop2)]})
    assert bad.status_code==409 and 'correlation_id' in bad.json()
    missing=client.post(f'/api/v1/floors/{uuid4()}/rooms',json=new_room())
    assert missing.status_code==404
    assert client.get('/api/v1/rooms').json()['items']==[]


def test_idempotent_bulk_replay_and_conflict(client):
    pid,bid,fid=setup_tree(client)
    body={'rooms':[new_room('A1'),new_room('A2')]}
    one=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json=body,headers={'Idempotency-Key':'key-123'})
    two=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json=body,headers={'Idempotency-Key':'key-123'})
    assert one.status_code==two.status_code==201
    assert [x['id'] for x in one.json()]==[x['id'] for x in two.json()]
    three=client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room('A3')]},headers={'Idempotency-Key':'key-123'})
    assert three.status_code==409


def test_pagination_filter_validation(client):
    pid,bid,fid=setup_tree(client)
    client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room('A1'),new_room('A2')]})
    assert client.get('/api/v1/rooms',params={'page':2,'page_size':1}).json()['meta']['total']==2
    assert len(client.get('/api/v1/rooms',params={'page':2,'page_size':1}).json()['items'])==1
    assert client.get('/api/v1/rooms',params={'page':0}).status_code==422
    assert client.get('/api/v1/rooms',params={'page_size':101}).status_code==422
    assert client.get('/api/v1/rooms',params={'occupancy':'OCCUPIED'}).json()['meta']['total']==0
    assert client.get('/api/v1/rooms',params={'occupancy':'VACANT'}).json()['meta']['total']==2
    assert client.get('/api/v1/rooms',params={'status':'BOGUS'}).status_code==422
    assert client.patch(f'/api/v1/rooms/{uuid4()}',json={'room_code':'Z'}).status_code==404
    assert client.get('/api/v1/properties/not-a-uuid').status_code==422


def test_patch_disallows_moving_parents_and_occupancy(client):
    pid,bid,fid=setup_tree(client)
    room=client.post(f'/api/v1/floors/{fid}/rooms',json=new_room()).json()
    rid=room['id']
    for field in ('floor_id','property_id','occupancy_contract_id'):
        assert client.patch(f'/api/v1/rooms/{rid}',json={field:str(uuid4())}).status_code==422
    assert client.patch(f'/api/v1/buildings/{bid}',json={'property_id':str(uuid4())}).status_code==422
    assert client.patch(f'/api/v1/floors/{fid}',json={'building_id':str(uuid4())}).status_code==422
    assert client.patch(f'/api/v1/rooms/{rid}',json={}).status_code==422
    assert client.patch(f'/api/v1/rooms/{rid}',json={'listed_rent':-1}).status_code==422
    assert client.patch(f'/api/v1/rooms/{rid}',json={'area_m2':'0.001'}).status_code==422
    assert client.patch(f'/api/v1/properties/{pid}',json={'name':None}).status_code==422


def test_duplicate_building_floor_and_name_length(client):
    pid,bid,fid=setup_tree(client)
    assert client.post(f'/api/v1/properties/{pid}/buildings',json={'name':'Dãy A'}).status_code==409
    assert client.post(f'/api/v1/buildings/{bid}/floors',json={'floor_number':1}).status_code==409
    assert client.post('/api/v1/properties',json={'name':'','address':'  '}).status_code==422
    assert client.post(f'/api/v1/floors/{fid}/rooms',json=new_room('bad space')).status_code==422
    assert client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[]}).status_code==422
    assert client.post(f'/api/v1/floors/{fid}/rooms/bulk',json={'rooms':[new_room(str(i)) for i in range(101)]}).status_code==422


def test_internal_service_token_and_validation(client):
    pid,bid,fid=setup_tree(client)
    room=client.post(f'/api/v1/floors/{fid}/rooms',json=new_room()).json()
    rid=room['id']
    path=f'/internal/v1/rooms/{rid}/validation'
    assert client.get(path).status_code==403
    assert client.get(path,headers={'X-Service-Token':'x'*32}).status_code==403
    ok=client.get(path,headers={'X-Service-Token':'a'*32})
    assert ok.status_code==200 and ok.json()['operational'] and ok.json()['property_id']==pid
    bad=client.get(f'/internal/v1/rooms/{uuid4()}/validation',headers={'X-Service-Token':'a'*32})
    assert bad.status_code==200 and bad.json()['exists'] is False


def test_openapi_and_health(client,monkeypatch):
    from app import main
    assert client.get('/health').json()=={'status':'ok'}
    assert 'internal/v1' not in str(client.get('/openapi.json').json()['paths'])
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def execute(self,*a):return self
        def scalar_one_or_none(self):return 'room_v3_003'
    class Engine:
        def connect(self):return Conn()
    monkeypatch.setattr(main,'get_engine',lambda:Engine())
    assert client.get('/ready').status_code==200
    class Unready:
        def connect(self):return Conn2()
    class Conn2(Conn):
        def scalar_one_or_none(self):return None
    monkeypatch.setattr(main,'get_engine',lambda:Unready())
    assert client.get('/ready').status_code==503

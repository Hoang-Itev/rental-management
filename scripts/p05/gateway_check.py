"""Manual owner E2E through Nginx; persists one demo tree in LOCAL database."""
from __future__ import annotations
import json,os,time,sys
from datetime import datetime,timedelta,timezone
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from uuid import uuid4

BASE=os.getenv('TEST_AUTH_BASE_URL','http://127.0.0.1:8080')


def call(method,path,body=None,token=None):
    headers={'Accept':'application/json','Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:
        with urlopen(req,timeout=15) as response:
            return response.status,json.load(response)
    except HTTPError as exc:
        return exc.code,{'error':exc.read()[:400].decode(errors='replace')}


def ok(method,path,body=None,token=None,status=200):
    code,result=call(method,path,body,token)
    assert code==status,(path,code,result)
    return result


def until(check,timeout=30):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        if check():return
        time.sleep(.7)
    raise AssertionError('Timed out waiting for Room projection')


def main():
    token=ok('POST','/api/v1/auth/login',{'email':os.environ['TEST_AUTH_EMAIL'],
                                        'password':os.environ['TEST_AUTH_PASSWORD']})['access_token']
    print('[PASS] JWT login through Nginx')
    suffix=uuid4().hex[:9]
    prop=ok('POST','/api/v1/properties',{'name':'P05 Demo '+suffix,'address':'Local demo only'},token,201)
    building=ok('POST',f"/api/v1/properties/{prop['id']}/buildings",{'name':'A'},token,201)
    floor=ok('POST',f"/api/v1/buildings/{building['id']}/floors",{'floor_number':1},token,201)
    room=ok('POST',f"/api/v1/floors/{floor['id']}/rooms",{
        'room_code':'P05A1','area_m2':'24.00','listed_rent':2500000},token,201)
    payer=ok('POST','/api/v1/tenants',{'full_name':'P05 '+suffix,'email':'p05-'+suffix+'@example.org'},token,201)
    today=datetime.now(timezone(timedelta(hours=7))).date()
    start=today-timedelta(days=2)
    end=today+timedelta(days=8)
    draft=ok('POST','/api/v1/contracts',{
        'contract_code':'P05-'+suffix,'room_id':room['id'],
        'representative_tenant_id':payer['id'],
        'start_date':start.isoformat(),'end_date':end.isoformat(),
        'initial_terms':{'effective_from':start.isoformat(),
                         'monthly_rent':2500000,'electricity_unit_price':3500,
                         'water_unit_price':18000}},token,201)
    assert ok('POST',f"/api/v1/contracts/{draft['id']}/confirm",{},token)['status']=='SCHEDULED'
    print('[PASS] DRAFT -> SCHEDULED')
    ok('POST','/api/v1/jobs/contracts/lifecycle/run',{'as_of':datetime.now(timezone.utc).isoformat()},token,202)
    until(lambda: ok('GET',f"/api/v1/rooms/{room['id']}",token=token)['occupancy_contract_id']==draft['id'])
    print('[PASS] SCHEDULED -> ACTIVE -> Room occupancy via RabbitMQ')
    ended=ok('POST',f"/api/v1/contracts/{draft['id']}/end",{
        'actual_end_date':(today-timedelta(days=1)).isoformat(),
        'reason':'P05 demo early return'},token)
    assert ended['status']=='ENDED'
    until(lambda: ok('GET',f"/api/v1/rooms/{room['id']}",token=token)['occupancy_contract_id'] is None)
    print('[PASS] ContractEnded -> Room vacant (effective boundary due)')
    print('ROOM_ID='+room['id'])
    print('CONTRACT_ID='+draft['id'])
    print('P05 GATEWAY CHECKPOINT OK (persistent local demo data created)')

if __name__=='__main__':
    try:main()
    except (AssertionError,KeyError,OSError,ValueError) as exc:
        print('P05 GATEWAY FAILED: '+str(exc),file=sys.stderr)
        sys.exit(1)

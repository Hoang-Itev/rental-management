"""Manual persistent local checkpoint through Nginx: owner login, room, tenant, contract.
Writes data into the user's current development database; it NEVER deletes it.
"""
from __future__ import annotations
import json,os,sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from uuid import uuid4

BASE=os.getenv('TEST_AUTH_BASE_URL','http://127.0.0.1:8080')

def req(method,path,body=None,token=None):
    headers={'Accept':'application/json','Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    data=json.dumps(body).encode() if body is not None else None
    request=Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urlopen(request,timeout=15) as res:
            return res.status,json.load(res)
    except HTTPError as exc:
        text=exc.read()[:350].decode('utf-8',errors='replace')
        return exc.code,{'error':text}

def ok(method,path,body=None,token=None,status=200):
    code,data=req(method,path,body,token)
    if code!=status: raise AssertionError(f'{path}: HTTP {code} {data}')
    return data

def main():
    login=ok('POST','/api/v1/auth/login',{'email':os.environ['TEST_AUTH_EMAIL'],
                                            'password':os.environ['TEST_AUTH_PASSWORD']})
    token=login['access_token']
    print('[PASS] owner login via Nginx')
    suffix=uuid4().hex[:10]
    prop=ok('POST','/api/v1/properties',{'name':'P04 Demo '+suffix,'address':'Local P04 test'},token,201)
    building=ok('POST',f"/api/v1/properties/{prop['id']}/buildings",{'name':'A'},token,201)
    floor=ok('POST',f"/api/v1/buildings/{building['id']}/floors",{'floor_number':1},token,201)
    room=ok('POST',f"/api/v1/floors/{floor['id']}/rooms",{
        'room_code':'R101','area_m2':'22.00','listed_rent':2500000},token,201)
    print('[PASS] owner creates room')
    payer=ok('POST','/api/v1/tenants',{'full_name':'P04 Demo Tenant '+suffix,
         'email':'tenant-'+suffix+'@example.com'},token,201)
    contract=ok('POST','/api/v1/contracts',{
         'contract_code':'P04-'+suffix,'room_id':room['id'],
         'representative_tenant_id':payer['id'],'start_date':'2027-01-01',
         'end_date':'2027-03-31',
         'initial_terms':{'effective_from':'2027-01-01','monthly_rent':2500000,
             'electricity_unit_price':3500,'water_unit_price':18000}},token,201)
    assert contract['status']=='DRAFT'
    confirmed=ok('POST',f"/api/v1/contracts/{contract['id']}/confirm",{},token)
    assert confirmed['status']=='SCHEDULED'
    print('[PASS] DRAFT -> SCHEDULED via real Room REST and tenant_db')
    again=ok('POST',f"/api/v1/contracts/{contract['id']}/confirm",{},token)
    assert again['status']=='SCHEDULED'
    assert ok('GET',f"/api/v1/contracts/{contract['id']}/terms",token=token)['meta']['total']==1
    overlapping=ok('POST','/api/v1/contracts',{
         'contract_code':'P04-OVER-'+suffix,'room_id':room['id'],
         'representative_tenant_id':payer['id'],'start_date':'2027-03-31',
         'end_date':'2027-04-15',
         'initial_terms':{'effective_from':'2027-03-31','monthly_rent':2500000,
             'electricity_unit_price':3500,'water_unit_price':18000}},token,201)
    code,_=req('POST',f"/api/v1/contracts/{overlapping['id']}/confirm",{},token)
    assert code==409,f'Expected 409 overlap, got {code}'
    print('[PASS] overlapping contract rejected; repeat confirm idempotent')
    meter_path = f"/api/v1/rooms/{room['id']}/meters"
    assert req('GET', meter_path)[0] == 401
    assert isinstance(ok('GET', meter_path, token=token)['items'], list)
    assert req('GET', '/api/v1/contracts/expiring')[0] == 401
    assert isinstance(ok('GET', '/api/v1/contracts/expiring', token=token)['items'], list)
    cancel_path = f"/api/v1/contracts/{overlapping['id']}/cancel"
    assert req('POST', cancel_path, {'reason': 'Gateway test cleanup'})[0] == 401
    assert ok('POST', cancel_path, {'reason': 'Gateway test cleanup'}, token)['status'] == 'CANCELLED'
    assert ok('POST', cancel_path, {'reason': 'Retry'}, token)['status'] == 'CANCELLED'
    print('[PASS] room meters, expiring contracts and idempotent cancellation through Nginx/JWT')
    print('ROOM_ID='+room['id'])
    print('TENANT_ID='+payer['id'])
    print('CONTRACT_ID='+contract['id'])
    print('P04 GATEWAY CHECKPOINT OK (created persistent local demo records)')

if __name__=='__main__':
    try:main()
    except (AssertionError,KeyError,OSError,ValueError) as exc:
        print('P04 GATEWAY FAILED: '+str(exc),file=sys.stderr)
        sys.exit(1)

"""Read-only local JWT + Nginx smoke for P06; requires a preexisting meter."""
from __future__ import annotations
import json
import os
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE=os.environ.get('TEST_AUTH_BASE_URL','http://127.0.0.1:8080')

def request(method,path,body=None,token=None):
    headers={'Accept':'application/json','Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,
                method=method,headers=headers)
    try:
        with urlopen(req,timeout=10) as response:
            return response.status,json.load(response)
    except HTTPError as exc:
        return exc.code,{'error':exc.read(300).decode(errors='replace')}

def main():
    meter_id=os.environ['P06_METER_ID']
    path=f'/api/v1/meters/{meter_id}/readings'
    unauth,_=request('GET',path)
    assert unauth in (401,403),f'Gateway did not enforce JWT: HTTP {unauth}'
    code,response=request('POST','/api/v1/auth/login',{
        'email':os.environ['TEST_AUTH_EMAIL'],
        'password':os.environ['TEST_AUTH_PASSWORD']})
    assert code==200,(code,response)
    token=response['access_token']
    deadline=time.monotonic()+45
    while True:
        code,data=request('GET',path,token=token)
        assert code==200,(code,data)
        if data['meta']['total']>0:break
        if time.monotonic()>deadline:
            raise AssertionError('No meter readings after 45s; check Simulator/worker logs')
        time.sleep(1)
    print('[PASS] JWT owner can GET real meter readings via Nginx')
    code,alarms=request('GET','/api/v1/meter-alerts',token=token)
    assert code==200 and 'items' in alarms,(code,alarms)
    print('[PASS] JWT owner can GET meter alerts via Nginx')
    print('P06 GATEWAY READ-ONLY CHECK OK')

if __name__=='__main__':
    try:main()
    except (AssertionError,KeyError,ValueError,OSError) as exc:
        print('P06 GATEWAY FAILED: '+str(exc),file=sys.stderr)
        sys.exit(1)

"""Read-only Room service E2E via real Nginx and Auth. Never creates or edits data."""
from __future__ import annotations
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen

BASE=os.getenv('TEST_AUTH_BASE_URL','http://127.0.0.1:8080').rstrip('/')
EMAIL=os.getenv('TEST_AUTH_EMAIL','')
PASSWORD=os.getenv('TEST_AUTH_PASSWORD','')


def call(path, *, token=None, body=None):
    headers={'Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    payload=None
    if body is not None:
        headers['Content-Type']='application/json'
        payload=json.dumps(body).encode()
    req=Request(BASE+path,data=payload,headers=headers,method='POST' if body is not None else 'GET')
    try:
        with urlopen(req,timeout=15) as res:return res.status,res.headers.get('Content-Type',''),res.read()
    except HTTPError as ex:return ex.code,ex.headers.get('Content-Type',''),ex.read()


def check(condition,message):
    if not condition:raise AssertionError(message)
    print('[PASS] '+message)


def main():
    if not EMAIL or not PASSWORD:
        print('TEST_AUTH_EMAIL and TEST_AUTH_PASSWORD required',file=sys.stderr)
        return 2
    try:
        status,typ,_=call('/api/v1/rooms')
        check(status==401,'unauthenticated rooms rejected 401')
        status,typ,_=call('/api/v1/rooms',token='invalid.invalid.invalid')
        check(status==401,'invalid JWT rejected 401')
        status,_,body=call('/api/v1/auth/login',body={'email':EMAIL,'password':PASSWORD})
        check(status==200,'login owner 200')
        jwt=json.loads(body)['access_token']
        for route in ['/api/v1/properties','/api/v1/rooms']:
            status,typ,body=call(route,token=jwt)
            check(status==200 and 'application/json' in typ and 'items' in json.loads(body) and 'meta' in json.loads(body),route+' routed through Nginx 200')
        status,_,_=call('/internal/v1/rooms/00000000-0000-0000-0000-000000000001/validation')
        check(status==404,'internal room validation not exposed publicly')
        print('ROOM GATEWAY E2E OK (6 checks, read-only)')
        return 0
    except (AssertionError,URLError,ValueError,KeyError) as exc:
        print('ROOM GATEWAY E2E FAILED: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())

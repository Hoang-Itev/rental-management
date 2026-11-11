"""P06 simulator: deterministic cumulative values, real timestamps, HTTP pagination."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import httpx
import pytest
from app.config import Settings
from app.meter_client import MeterClient
from app.virtual_clock import VirtualClock, canonical_time
from app.main import emit_once

@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv('SERVICE_TOKEN','a'*32)
    monkeypatch.setenv('MQTT_USERNAME','test')
    monkeypatch.setenv('MQTT_PASSWORD','testsecret')
    return Settings.from_env()

def test_virtual_clock_monotone_restart_and_no_future_timestamps(config):
    mid=uuid4()
    first=datetime(2026,11,11,8,0,0,991123,tzinfo=timezone.utc)
    next_=first+timedelta(hours=2)
    original=VirtualClock(config).reading(mid,'ELECTRICITY',first)
    restarted=VirtualClock(config).reading(mid,'ELECTRICITY',next_)
    assert restarted > original >= 0
    assert original == VirtualClock(config).reading(mid,'ELECTRICITY',first)
    assert canonical_time(first).microsecond == 0
    assert canonical_time(first).tzinfo == timezone.utc
    with pytest.raises(ValueError):VirtualClock(config).reading(mid,'INVALID',first)

def test_http_client_active_meters_paged_and_authenticated(config):
    rooms=[uuid4(),uuid4()]
    ids=[uuid4(),uuid4()]
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.headers['X-Service-Token']=='a'*32
        page=int(request.url.params['page'])
        if page==1:
            return httpx.Response(200,json={'items':[{'id':str(ids[0]),'room_id':str(rooms[0]),'meter_type':'ELECTRICITY','status':'ACTIVE'}], 'meta':{'total':2}})
        return httpx.Response(200,json={'items':[{'id':str(ids[1]),'room_id':str(rooms[1]),'meter_type':'WATER','status':'ACTIVE'}], 'meta':{'total':2}})
    data=MeterClient(config, transport=httpx.MockTransport(handler)).list_active()
    assert [m.id for m in data]==ids
    assert len(calls)==2

def test_http_bad_data_rejected_before_publish(config):
    def handler(req):
        return httpx.Response(200,json={'items':[{'id':str(uuid4()),'room_id':str(uuid4()),'meter_type':'INVALID','status':'ACTIVE'}], 'meta':{'total':1}})
    with pytest.raises(ValueError):MeterClient(config,transport=httpx.MockTransport(handler)).list_active()


def test_emit_once_uses_same_real_timestamp_and_qos_pub_api(config):
    mid1,mid2=uuid4(),uuid4()
    from app.meter_client import Meter
    class M:
        def list_active(self):return [Meter(mid1,uuid4(),'ELECTRICITY'),Meter(mid2,uuid4(),'WATER')]
    class P:
        def __init__(self):self.events=[]
        def publish(self,*args):self.events.append(args)
    now=datetime(2026,11,11,11,0,tzinfo=timezone.utc)
    publisher=P()
    assert emit_once(config,M(),publisher,instant=now)==2
    assert len(publisher.events)==2
    assert all(e[1]==now.isoformat() for e in publisher.events)
    assert all(Decimal(e[2])>=0 for e in publisher.events)


def test_settings_rejects_invalid_scale(monkeypatch):
    monkeypatch.setenv('SERVICE_TOKEN','a'*32)
    monkeypatch.setenv('MQTT_USERNAME','test')
    monkeypatch.setenv('MQTT_PASSWORD','testsecret')
    monkeypatch.setenv('SIM_TIME_SCALE','0')
    with pytest.raises(ValueError):Settings.from_env()

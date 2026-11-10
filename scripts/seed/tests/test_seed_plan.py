import importlib.util
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import seed_service as seed


def test_inventory_and_links():
    d=seed.dataset()
    assert d['version']=='demo_v1'
    assert len(d['rooms'])==12 and len(set(d['rooms']))==12
    assert len(d['tenants'])==8 and len(d['contracts'])==6
    assert len(d['issued_rooms'])==4 and len(d['blocked_rooms'])==2
    assert set(d['occupied_rooms'])==set(c['room_code'] for c in d['contracts'])
    assert set(d['issued_rooms']).isdisjoint(d['blocked_rooms'])
    for c in d['contracts']:
        assert c['room_code'] in d['rooms']
        assert 0 <= c['tenant_index'] < len(d['tenants'])


def test_identifiers_stable_and_unique():
    d=seed.dataset()
    a=[seed.sid('room',r) for r in d['rooms']]
    assert len(set(a))==len(a)
    assert a==[seed.sid('room',r) for r in d['rooms']]
    assert seed.sid('room','A101')!=seed.sid('contract','A101')


def test_amounts_and_rates():
    d=seed.dataset()
    for room in d['rooms']:
        assert seed.money_for_room(room,d)>0
        for kind in ('ELECTRICITY','WATER'):
            assert seed.delta_meter_value(room,kind,d)>0
            assert seed.initial_meter_value(room,kind,d)>0


def test_business_period_end_exclusive():
    from datetime import date
    d=seed.dataset()
    assert date.fromisoformat(d['billing_month']) < date.fromisoformat(d['period_end'])
    assert seed.midnight_vn('2026-10-01').isoformat()=='2026-09-30T17:00:00+00:00'

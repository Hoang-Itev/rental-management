"""P05 Room stale event and handover order invariants."""
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import select,func
from app.service import RoomService
from app import models as m,schemas as s
from app.lifecycle import apply_contract_event,FutureEvent
import pytest


def message(kind, contract, room, when, eid=None):
    return {'event_id':str(eid or uuid4()),'event_type':kind,'event_version':1,
            'aggregate_id':str(contract),'occurred_at':when,'effective_at':when,
            'correlation_id':str(uuid4()),'data':{'contract_id':str(contract),'room_id':str(room)}}


def test_handover_both_message_orders(make_session,tree):
    with make_session() as db:
        room=RoomService(db).create_rooms(tree['floor'],s.RoomBulkCreate(rooms=[s.RoomCreateItem(room_code='A101',area_m2='20',listed_rent=100)]))[0]
        db.commit()
        rid=room.id
    for reverse in [False,True]:
        with make_session() as db:
            obj=db.get(m.Room,rid)
            obj.occupancy_contract_id=None;obj.occupancy_updated_at=None
            db.commit()
        a,b=uuid4(),uuid4()
        old=message('ContractStarted',a,rid,'2026-11-01T00:00:00+07:00')
        end=message('ContractEnded',a,rid,'2026-11-16T00:00:00+07:00')
        start=message('ContractStarted',b,rid,'2026-11-16T00:00:00+07:00')
        with make_session() as db:
            assert apply_contract_event(db,old,now=datetime(2026,11,20,tzinfo=timezone.utc))=='applied'
            for item in ([start,end] if reverse else [end,start]):
                apply_contract_event(db,item,now=datetime(2026,11,20,tzinfo=timezone.utc))
            assert db.get(m.Room,rid).occupancy_contract_id==b
            # Old START A cannot roll back newer B occupancy.
            apply_contract_event(db,old | {'event_id':str(uuid4())},now=datetime(2026,11,20,tzinfo=timezone.utc))
            assert db.get(m.Room,rid).occupancy_contract_id==b
            assert apply_contract_event(db,start,now=datetime(2026,11,20,tzinfo=timezone.utc))=='duplicate'


def test_future_event_never_applied(make_session,tree):
    with make_session() as db:
        room=RoomService(db).create_rooms(tree['floor'],s.RoomBulkCreate(rooms=[s.RoomCreateItem(room_code='A101',area_m2='20',listed_rent=100)]))[0]
        event=message('ContractStarted',uuid4(),room.id,'2027-11-01T00:00:00+07:00')
        with pytest.raises(FutureEvent):
            apply_contract_event(db,event,now=datetime(2026,11,11,tzinfo=timezone.utc))
        assert db.get(m.Room,room.id).occupancy_contract_id is None


def test_invalid_timestamps_and_missing_room(make_session):
    from pydantic import ValidationError
    a, rid = uuid4(), uuid4()
    item = message('ContractStarted', a, rid, '2026-11-11T00:00:00+07:00')
    with make_session() as db:
        with pytest.raises(LookupError):
            apply_contract_event(db, item, now=datetime(2026,11,12,tzinfo=timezone.utc))
        with pytest.raises(ValueError):
            apply_contract_event(db, item, now=datetime(2026,11,12))
        with pytest.raises(ValidationError):
            apply_contract_event(db, item | {'aggregate_id':str(uuid4())})
        with pytest.raises(ValidationError):
            apply_contract_event(db, item | {'effective_at':'2026-11-11T00:00:00'})


def test_duplicate_contract_and_equal_time_different_contract(make_session,tree):
    with make_session() as db:
        room=RoomService(db).create_rooms(tree['floor'],s.RoomBulkCreate(rooms=[s.RoomCreateItem(room_code='A101',area_m2='20',listed_rent=100)]))[0]
        a,b=uuid4(),uuid4()
        stamp='2026-11-10T00:00:00+07:00'
        apply_contract_event(db,message('ContractStarted',a,room.id,stamp),now=datetime(2026,11,12,tzinfo=timezone.utc))
        assert apply_contract_event(db,message('ContractStarted',a,room.id,stamp),now=datetime(2026,11,12,tzinfo=timezone.utc))=='duplicate-contract'
        with pytest.raises(ValueError,match='Conflicting start'):
            apply_contract_event(db,message('ContractStarted',b,room.id,stamp),now=datetime(2026,11,12,tzinfo=timezone.utc))
        assert db.get(m.Room,room.id).occupancy_contract_id==a


def test_end_before_any_start_then_start_same_instant(make_session,tree):
    with make_session() as db:
        room=RoomService(db).create_rooms(tree['floor'],s.RoomBulkCreate(rooms=[s.RoomCreateItem(room_code='A101',area_m2='20',listed_rent=100)]))[0]
        stamp='2026-11-10T00:00:00+07:00'
        a,b=uuid4(),uuid4()
        assert apply_contract_event(db,message('ContractEnded',a,room.id,stamp),now=datetime(2026,11,12,tzinfo=timezone.utc))=='applied-empty'
        assert apply_contract_event(db,message('ContractStarted',b,room.id,stamp),now=datetime(2026,11,12,tzinfo=timezone.utc))=='applied'
        assert db.get(m.Room,room.id).occupancy_contract_id==b

"""P02 integration: MUST run only in isolated PostgreSQL test Compose project.

The test runner sets ROOM_P02_EPHEMERAL_TEST=1 and creates a new -p project.
No persistent local rental-management data is modified.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m, schemas as s, repository as repo
from app.db import get_engine
from app.service import RoomError, RoomService

if os.getenv('ROOM_P02_EPHEMERAL_TEST') != '1':
    raise RuntimeError('P02 PostgreSQL tests require isolated project and ROOM_P02_EPHEMERAL_TEST=1')


@pytest.fixture
def pg_session():
    engine = get_engine()
    conn = engine.connect()
    outer = conn.begin()
    try:
        with Session(bind=conn, join_transaction_mode='create_savepoint',
                     expire_on_commit=False, autoflush=False) as session:
            yield session
    finally:
        outer.rollback()
        conn.close()


def setup_tree(session):
    svc=RoomService(session)
    prop=svc.create_property(s.PropertyCreate(name='Integration '+str(uuid4()),address='Integration fixture'))
    building=svc.create_building(prop.id,s.BuildingCreate(name='A'))
    floor=svc.create_floor(building.id,s.FloorCreate(floor_number=1))
    return svc,prop,building,floor


def item(code):
    return s.RoomCreateItem(room_code=code,area_m2='22.00',listed_rent=1500000)


def test_postgres_real_bulk_commit_and_idempotency(pg_session):
    svc,prop,building,floor=setup_tree(pg_session)
    batch=s.RoomBulkCreate(rooms=[item('P1'),item('P2')])
    first=svc.create_rooms(floor.id,batch,'idempotent')
    assert len(first)==2
    assert [x.id for x in svc.create_rooms(floor.id,batch,'idempotent')]==[x.id for x in first]
    assert pg_session.scalar(select(func.count()).select_from(m.OutboxEvent).where(m.OutboxEvent.aggregate_type=='Room'))==2
    assert pg_session.scalar(select(func.count()).select_from(m.Room).where(m.Room.property_id==prop.id))==2


def test_real_unique_constraint_and_rollback(pg_session):
    svc,prop,building,floor=setup_tree(pg_session)
    svc.create_rooms(floor.id,s.RoomBulkCreate(rooms=[item('P1')]))
    before=pg_session.scalar(select(func.count()).select_from(m.Room).where(m.Room.property_id==prop.id))
    with pytest.raises(RoomError) as exc:
        svc.create_rooms(floor.id,s.RoomBulkCreate(rooms=[item('P2'),item('P1')]))
    assert exc.value.status==409
    assert pg_session.scalar(select(func.count()).select_from(m.Room).where(m.Room.property_id==prop.id))==before
    # Bypass service pre-check: PostgreSQL UNIQUE(property_id, room_code) still protects races.
    savepoint=pg_session.begin_nested()
    with pytest.raises(IntegrityError):
        repo.add(pg_session,m.Room(id=uuid4(),property_id=prop.id,floor_id=floor.id,
                                   room_code='P1',area_m2=22,listed_rent=1,status='ACTIVE'))
    savepoint.rollback()


def test_actual_postgres_property_guard(pg_session):
    svc,prop,building,floor=setup_tree(pg_session)
    other=svc.create_property(s.PropertyCreate(name='Unrelated',address='2 demo'))
    # Simulate bypassed application validation: PostgreSQL V3.1 trigger must reject it.
    savepoint=pg_session.begin_nested()
    with pytest.raises(IntegrityError) as exc:
        repo.add(pg_session,m.Room(id=uuid4(),property_id=other.id,floor_id=floor.id,
                                   room_code='BAD',area_m2=22,listed_rent=1,status='ACTIVE'))
    assert getattr(exc.value.orig,'sqlstate',None)=='23514'
    savepoint.rollback()


def test_immutable_building_floor_after_creation(pg_session):
    svc,prop,building,floor=setup_tree(pg_session)
    other=svc.create_property(s.PropertyCreate(name='Another',address='Other'))
    other_building=svc.create_building(other.id,s.BuildingCreate(name='New'))
    savepoint=pg_session.begin_nested()
    building.property_id=other.id
    with pytest.raises(IntegrityError) as exc:
        pg_session.flush()
    assert getattr(exc.value.orig,'sqlstate',None)=='23514'
    savepoint.rollback()
    pg_session.refresh(building)
    savepoint=pg_session.begin_nested()
    floor.building_id=other_building.id
    with pytest.raises(IntegrityError) as exc:
        pg_session.flush()
    assert getattr(exc.value.orig,'sqlstate',None)=='23514'
    savepoint.rollback()
    pg_session.refresh(floor)


def test_pg_outbox_failure_rolls_back_every_room(pg_session,monkeypatch):
    svc,prop,building,floor=setup_tree(pg_session)
    original=repo.add
    def fail_outbox(session,row):
        if isinstance(row,m.OutboxEvent):
            raise RuntimeError('broker outbox simulated failure')
        return original(session,row)
    monkeypatch.setattr(repo,'add',fail_outbox)
    with pytest.raises(RuntimeError,match='outbox'):
        svc.create_rooms(floor.id,s.RoomBulkCreate(rooms=[item('RB1'),item('RB2')]))
    assert pg_session.scalar(select(func.count()).select_from(m.Room).where(m.Room.property_id==prop.id))==0
    assert pg_session.scalar(select(func.count()).select_from(m.OutboxEvent))==0

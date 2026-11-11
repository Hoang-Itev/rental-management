from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app import models as m, schemas as s
from app.service import RoomError, RoomService
from conftest import unit_room


def created_tree(svc):
    p=svc.create_property(s.PropertyCreate(name="a",address="address"))
    b=svc.create_building(p.id,s.BuildingCreate(name="b"))
    f=svc.create_floor(b.id,s.FloorCreate(floor_number=0))
    return p,b,f


def test_crud_and_pagination(test_service):
    svc=test_service
    p,b,f=created_tree(svc)
    assert svc.get_property(p.id).name == "a"
    assert svc.get_building(b.id).property_id==p.id
    assert svc.get_floor(f.id).building_id==b.id
    assert svc.list_properties(1,10)[1] == 1
    assert svc.list_buildings(p.id,1,10)[1] == 1
    assert svc.list_floors(b.id,1,10)[1] == 1
    svc.patch_property(p.id,s.PropertyPatch(name="A2",description="ok"))
    svc.patch_building(b.id,s.BuildingPatch(name="B2"))
    svc.patch_floor(f.id,s.FloorPatch(name="F2"))
    assert svc.get_property(p.id).description=="ok"
    assert svc.get_building(b.id).name=="B2"
    assert svc.get_floor(f.id).name=="F2"


def test_bulk_writes_outbox_and_replays_without_duplicates(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    data=s.RoomBulkCreate(rooms=[unit_room("a101"),unit_room("a102")])
    out=svc.create_rooms(f.id,data,idempotency_key="req-1")
    assert [x.room_code for x in out]==["A101","A102"]
    assert svc.list_rooms(1,10,property_id=p.id)[1]==2
    events=svc.session.scalars(select(m.OutboxEvent)).all()
    assert len(events)==2
    assert all(e.event_type=="RoomCreated" and e.payload['data']['room_id']==str(e.aggregate_id) for e in events)
    assert len({e.payload['event_id'] for e in events})==2
    res=svc.create_rooms(f.id,data,idempotency_key="req-1")
    assert [x.id for x in res] == [x.id for x in out]
    assert svc.session.scalar(select(func.count()).select_from(m.OutboxEvent))==2
    with pytest.raises(RoomError) as ei:
        svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A999")]),idempotency_key="req-1")
    assert ei.value.status==409


def test_duplicate_existing_in_later_item_rolls_back_all(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A100")]))
    with pytest.raises(RoomError) as ei:
        svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A101"),unit_room("A100")]))
    assert ei.value.status==409
    assert svc.list_rooms(1,10)[1]==1
    assert svc.session.scalar(select(func.count()).select_from(m.OutboxEvent))==1


def test_db_failure_mid_batch_rolls_back_rooms_and_events(test_service, monkeypatch):
    svc=test_service;p,b,f=created_tree(svc)
    from app import repository
    original=repository.add
    counter=0
    def failing_add(session, entity):
        nonlocal counter
        counter += 1
        if counter == 4:  # two Rooms and first Outbox inserted, then fails
            raise ValueError("simulate outbox write failure")
        return original(session,entity)
    monkeypatch.setattr(repository,"add",failing_add)
    with pytest.raises(ValueError,match="simulate"):
        svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A1"),unit_room("A2"),unit_room("A3")]))
    assert svc.session.scalar(select(func.count()).select_from(m.Room))==0
    assert svc.session.scalar(select(func.count()).select_from(m.OutboxEvent))==0


def test_wrong_property_in_payload_rejected(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    other=svc.create_property(s.PropertyCreate(name="Other",address="2 Street"))
    with pytest.raises(RoomError,match="does not belong"):
        svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A1",other.id)]))
    assert svc.list_rooms(1,10)[1]==0


def test_missing_and_inactive_hierarchy(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    with pytest.raises(RoomError) as e:
        svc.create_rooms(uuid4(),s.RoomBulkCreate(rooms=[unit_room()]))
    assert e.value.status==404
    svc.patch_floor(f.id,s.FloorPatch(status="INACTIVE"))
    with pytest.raises(RoomError,match="inactive"):
        svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room()]))
    svc.patch_building(b.id,s.BuildingPatch(status="INACTIVE"))
    with pytest.raises(RoomError):
        svc.create_floor(b.id,s.FloorCreate(floor_number=2))
    with pytest.raises(RoomError):
        svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room()]))
    with pytest.raises(RoomError):
        svc.patch_floor(f.id,s.FloorPatch(status="ACTIVE"))


def test_property_inactive_rejects_creating_building(test_service):
    svc=test_service
    p=svc.create_property(s.PropertyCreate(name="p",address="x"))
    svc.patch_property(p.id,s.PropertyPatch(status="INACTIVE"))
    with pytest.raises(RoomError,match="inactive"):
        svc.create_building(p.id,s.BuildingCreate(name="b"))


def test_deactivate_safeguards(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    with pytest.raises(RoomError,match="buildings"):
        svc.deactivate("property",p.id)
    with pytest.raises(RoomError,match="floors"):
        svc.deactivate("building",b.id)
    rooms=svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room()]))
    with pytest.raises(RoomError,match="rooms"):
        svc.deactivate("floor",f.id)
    svc.deactivate("room",rooms[0].id)
    assert svc.get_room(rooms[0].id).status=="INACTIVE"
    svc.deactivate("room",rooms[0].id)  # idempotent
    svc.deactivate("floor",f.id)
    svc.deactivate("building",b.id)
    svc.deactivate("property",p.id)
    assert svc.get_property(p.id).status=="INACTIVE"


def test_occupied_room_cannot_be_deactivated(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    room=svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room()]))[0]
    with svc.session.begin():
        stored=svc.session.get(m.Room,room.id)
        stored.occupancy_contract_id=uuid4()
    with pytest.raises(RoomError,match="occupied"):
        svc.patch_room(room.id,s.RoomPatch(status="INACTIVE"))


def test_room_status_and_filters(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    rooms=svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A1"),unit_room("A2")]))
    assert svc.validate_room(rooms[0].id).operational
    assert not svc.validate_room(uuid4()).exists
    svc.patch_room(rooms[0].id,s.RoomPatch(status="INACTIVE"))
    assert not svc.validate_room(rooms[0].id).operational
    assert svc.list_rooms(1,10,occupancy="INACTIVE")[1]==1
    assert svc.list_rooms(1,10,occupancy="VACANT")[1]==1
    assert svc.list_rooms(1,10,status="ACTIVE")[1]==1
    assert svc.list_rooms(1,1)[1]==2
    assert len(svc.list_rooms(2,1)[0])==1
    svc.patch_room(rooms[0].id,s.RoomPatch(status="ACTIVE",room_code="A5",listed_rent=123))
    assert svc.get_room(rooms[0].id).room_code=="A5"
    assert svc.list_rooms(1,10,occupancy="INACTIVE")[1]==0


def test_duplicate_room_patch_conflicts(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    a,bb=svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room("A1"),unit_room("A2")]))
    with pytest.raises(RoomError) as ei:
        svc.patch_room(bb.id,s.RoomPatch(room_code="a1"))
    assert ei.value.status==409


def test_duplicate_building_and_floor_conflicts(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    with pytest.raises(RoomError) as ei:
        svc.create_building(p.id,s.BuildingCreate(name="b"))
    assert ei.value.status==409
    with pytest.raises(RoomError) as ei:
        svc.create_floor(b.id,s.FloorCreate(floor_number=0))
    assert ei.value.status==409


def test_validation_with_parent_disabled(test_service):
    svc=test_service;p,b,f=created_tree(svc)
    room=svc.create_rooms(f.id,s.RoomBulkCreate(rooms=[unit_room()]))[0]
    with svc.session.begin():
        svc.session.get(m.Property,p.id).status="INACTIVE" # simulate imported legacy mismatch
    assert not svc.validate_room(room.id).operational


def test_missing_entities(test_service):
    svc=test_service
    for fn in [svc.get_property, svc.get_building, svc.get_floor, svc.get_room]:
        with pytest.raises(RoomError) as e: fn(uuid4())
        assert e.value.status==404
    with pytest.raises(RoomError): svc.list_buildings(uuid4(),1,10)
    with pytest.raises(RoomError): svc.list_floors(uuid4(),1,10)

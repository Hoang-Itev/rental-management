"""External owner routes. Nginx runs auth_request before forwarding to Room."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from app import schemas as s
from app.db import get_db
from app.service import RoomService

router = APIRouter(prefix="/api/v1", tags=["Room"])
Db = Annotated[Session, Depends(get_db)]
PageNum = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def service(db: Session) -> RoomService:
    return RoomService(db)


def as_page(rows, count, page: int, page_size: int, factory):
    return {"items": [factory(r) for r in rows], "meta": {"page": page, "page_size": page_size, "total": count}}


def trace_id(request: Request) -> UUID:
    try:
        return UUID(request.headers.get("x-correlation-id", ""))
    except (ValueError, TypeError):
        return uuid4()


@router.get("/properties", response_model=s.Page[s.PropertyOut])
def properties(db: Db, page: PageNum = 1, page_size: PageSize = 20):
    rows, count = service(db).list_properties(page, page_size)
    return as_page(rows, count, page, page_size, s.PropertyOut.model_validate)


@router.post("/properties", response_model=s.PropertyOut, status_code=201)
def add_property(body: s.PropertyCreate, db: Db):
    return service(db).create_property(body)


@router.get("/properties/{property_id}", response_model=s.PropertyOut)
def property_detail(property_id: UUID, db: Db):
    return service(db).get_property(property_id)


@router.patch("/properties/{property_id}", response_model=s.PropertyOut)
def edit_property(property_id: UUID, body: s.PropertyPatch, db: Db):
    return service(db).patch_property(property_id, body)


@router.delete("/properties/{property_id}", status_code=204)
def delete_property(property_id: UUID, db: Db):
    service(db).deactivate("property", property_id)
    return Response(status_code=204)


@router.get("/properties/{property_id}/buildings", response_model=s.Page[s.BuildingOut])
def buildings(property_id: UUID, db: Db, page: PageNum = 1, page_size: PageSize = 20):
    rows, count = service(db).list_buildings(property_id, page, page_size)
    return as_page(rows, count, page, page_size, s.BuildingOut.model_validate)


@router.post("/properties/{property_id}/buildings", response_model=s.BuildingOut, status_code=201)
def add_building(property_id: UUID, body: s.BuildingCreate, db: Db):
    return service(db).create_building(property_id, body)


@router.get("/buildings/{building_id}", response_model=s.BuildingOut)
def building_detail(building_id: UUID, db: Db):
    return service(db).get_building(building_id)


@router.patch("/buildings/{building_id}", response_model=s.BuildingOut)
def edit_building(building_id: UUID, body: s.BuildingPatch, db: Db):
    return service(db).patch_building(building_id, body)


@router.delete("/buildings/{building_id}", status_code=204)
def delete_building(building_id: UUID, db: Db):
    service(db).deactivate("building", building_id)
    return Response(status_code=204)


@router.get("/buildings/{building_id}/floors", response_model=s.Page[s.FloorOut])
def floors(building_id: UUID, db: Db, page: PageNum = 1, page_size: PageSize = 20):
    rows, count = service(db).list_floors(building_id, page, page_size)
    return as_page(rows, count, page, page_size, s.FloorOut.model_validate)


@router.post("/buildings/{building_id}/floors", response_model=s.FloorOut, status_code=201)
def add_floor(building_id: UUID, body: s.FloorCreate, db: Db):
    return service(db).create_floor(building_id, body)


@router.get("/floors/{floor_id}", response_model=s.FloorOut)
def floor_detail(floor_id: UUID, db: Db):
    return service(db).get_floor(floor_id)


@router.patch("/floors/{floor_id}", response_model=s.FloorOut)
def edit_floor(floor_id: UUID, body: s.FloorPatch, db: Db):
    return service(db).patch_floor(floor_id, body)


@router.delete("/floors/{floor_id}", status_code=204)
def delete_floor(floor_id: UUID, db: Db):
    service(db).deactivate("floor", floor_id)
    return Response(status_code=204)


@router.post("/floors/{floor_id}/rooms/bulk", response_model=list[s.RoomOut], status_code=201)
def add_rooms(floor_id: UUID, body: s.RoomBulkCreate, db: Db, request: Request,
              idempotency_key: Annotated[str | None, Header(max_length=128, alias="Idempotency-Key")] = None):
    rows = service(db).create_rooms(floor_id, body, idempotency_key, trace_id(request))
    return [s.RoomOut.from_room(r) for r in rows]


@router.post("/floors/{floor_id}/rooms", response_model=s.RoomOut, status_code=201)
def add_one_room(floor_id: UUID, body: s.RoomCreateItem, db: Db, request: Request,
                 idempotency_key: Annotated[str | None, Header(max_length=128, alias="Idempotency-Key")] = None):
    rows = service(db).create_rooms(floor_id, s.RoomBulkCreate(rooms=[body]), idempotency_key, trace_id(request))
    return s.RoomOut.from_room(rows[0])


@router.get("/rooms", response_model=s.Page[s.RoomOut])
def rooms(db: Db, property_id: UUID | None = None, status: s.Status | None = None,
          occupancy: s.Occupancy | None = None, page: PageNum = 1, page_size: PageSize = 20):
    rows, count = service(db).list_rooms(page, page_size, property_id, status, occupancy)
    return as_page(rows, count, page, page_size, s.RoomOut.from_room)


@router.get("/rooms/{room_id}", response_model=s.RoomOut)
def room_detail(room_id: UUID, db: Db):
    return s.RoomOut.from_room(service(db).get_room(room_id))


@router.patch("/rooms/{room_id}", response_model=s.RoomOut)
def edit_room(room_id: UUID, body: s.RoomPatch, db: Db):
    return s.RoomOut.from_room(service(db).patch_room(room_id, body))


@router.delete("/rooms/{room_id}", status_code=204)
def delete_room(room_id: UUID, db: Db):
    service(db).deactivate("room", room_id)
    return Response(status_code=204)

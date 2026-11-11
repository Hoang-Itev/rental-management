"""Room domain rules and single-transaction writes, including transactional outbox."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m, repository as repo, schemas as s


class RoomError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def missing(label: str) -> RoomError:
    return RoomError(404, "NOT_FOUND", f"{label} not found")


def conflict(message: str) -> RoomError:
    return RoomError(409, "CONFLICT", message)


class RoomService:
    def __init__(self, session: Session):
        self.session = session

    @contextmanager
    def atomic(self):
        try:
            # A caller may have opened an implicit read transaction first.
            # In that case use a SAVEPOINT and let the caller own the outer TX.
            transaction = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
            with transaction:
                yield
        except IntegrityError as exc:
            # Unique, FK and check violations are expected races; don't leak DB internals.
            raise conflict("Database constraint violation") from exc

    def need(self, model, object_id: UUID, *, lock: bool = False):
        row = repo.get(self.session, model, object_id, lock=lock)
        if row is None:
            raise missing(model.__name__)
        return row

    def list_properties(self, page: int, page_size: int):
        return repo.page(self.session, m.Property, page_number=page, page_size=page_size, order_by=m.Property.name)

    def get_property(self, property_id: UUID):
        return self.need(m.Property, property_id)

    def create_property(self, data: s.PropertyCreate):
        with self.atomic():
            row = repo.add(self.session, m.Property(id=uuid4(), **data.model_dump()))
        return row

    def patch_property(self, property_id: UUID, data: s.PropertyPatch):
        with self.atomic():
            row = self.need(m.Property, property_id, lock=True)
            fields = data.model_dump(exclude_unset=True)
            if fields.get("status") == "INACTIVE" and row.status == "ACTIVE":
                if repo.any_active(self.session, m.Building, m.Building.property_id, property_id):
                    raise conflict("Deactivate active buildings first")
            for key, value in fields.items():
                setattr(row, key, value)
            self.session.flush()
        return row

    def list_buildings(self, property_id: UUID, page: int, page_size: int):
        self.need(m.Property, property_id)
        return repo.page(self.session, m.Building, page_number=page, page_size=page_size,
                         filters=(m.Building.property_id == property_id,), order_by=m.Building.name)

    def get_building(self, building_id: UUID):
        return self.need(m.Building, building_id)

    def create_building(self, property_id: UUID, data: s.BuildingCreate):
        with self.atomic():
            prop = self.need(m.Property, property_id, lock=True)
            if prop.status != "ACTIVE":
                raise conflict("Property is inactive")
            row = repo.add(self.session, m.Building(id=uuid4(), property_id=property_id, name=data.name, status="ACTIVE"))
        return row

    def patch_building(self, building_id: UUID, data: s.BuildingPatch):
        with self.atomic():
            row = self.need(m.Building, building_id, lock=True)
            fields = data.model_dump(exclude_unset=True)
            if fields.get("status") == "INACTIVE" and row.status == "ACTIVE":
                if repo.any_active(self.session, m.Floor, m.Floor.building_id, building_id):
                    raise conflict("Deactivate active floors first")
            if fields.get("status") == "ACTIVE" and row.status != "ACTIVE":
                if self.need(m.Property, row.property_id, lock=True).status != "ACTIVE":
                    raise conflict("Parent property is inactive")
            for key, value in fields.items():
                setattr(row, key, value)
            self.session.flush()
        return row

    def list_floors(self, building_id: UUID, page: int, page_size: int):
        self.need(m.Building, building_id)
        return repo.page(self.session, m.Floor, page_number=page, page_size=page_size,
                         filters=(m.Floor.building_id == building_id,), order_by=m.Floor.floor_number)

    def get_floor(self, floor_id: UUID):
        return self.need(m.Floor, floor_id)

    def create_floor(self, building_id: UUID, data: s.FloorCreate):
        with self.atomic():
            building = self.need(m.Building, building_id, lock=True)
            if building.status != "ACTIVE" or self.need(m.Property, building.property_id, lock=True).status != "ACTIVE":
                raise conflict("Building or property is inactive")
            row = repo.add(self.session, m.Floor(id=uuid4(), building_id=building_id, **data.model_dump(), status="ACTIVE"))
        return row

    def patch_floor(self, floor_id: UUID, data: s.FloorPatch):
        with self.atomic():
            row = self.need(m.Floor, floor_id, lock=True)
            fields = data.model_dump(exclude_unset=True)
            if fields.get("status") == "INACTIVE" and row.status == "ACTIVE":
                if repo.any_active(self.session, m.Room, m.Room.floor_id, floor_id):
                    raise conflict("Deactivate active rooms first")
            if fields.get("status") == "ACTIVE" and row.status != "ACTIVE":
                building = self.need(m.Building, row.building_id, lock=True)
                prop = self.need(m.Property, building.property_id, lock=True)
                if building.status != "ACTIVE" or prop.status != "ACTIVE":
                    raise conflict("Parent building or property is inactive")
            for key, value in fields.items():
                setattr(row, key, value)
            self.session.flush()
        return row

    def list_rooms(self, page: int, page_size: int, property_id: UUID | None = None,
                   status: s.Status | None = None, occupancy: s.Occupancy | None = None):
        filters = []
        if property_id is not None:
            filters.append(m.Room.property_id == property_id)
        if status is not None:
            filters.append(m.Room.status == status)
        if occupancy == "INACTIVE":
            filters.append(m.Room.status == "INACTIVE")
        elif occupancy == "OCCUPIED":
            filters.extend((m.Room.status == "ACTIVE", m.Room.occupancy_contract_id.is_not(None)))
        elif occupancy == "VACANT":
            filters.extend((m.Room.status == "ACTIVE", m.Room.occupancy_contract_id.is_(None)))
        return repo.page(self.session, m.Room, page_number=page, page_size=page_size,
                         filters=filters, order_by=m.Room.room_code)

    def get_room(self, room_id: UUID):
        return self.need(m.Room, room_id)

    def _floor_lineage(self, floor_id: UUID):
        floor = self.need(m.Floor, floor_id, lock=True)
        building = self.need(m.Building, floor.building_id, lock=True)
        prop = self.need(m.Property, building.property_id, lock=True)
        if any(row.status != "ACTIVE" for row in (floor, building, prop)):
            raise conflict("Floor, building or property is inactive")
        return floor, building, prop

    @staticmethod
    def _idempotency_key(floor_id: UUID, key: str | None) -> str | None:
        if key is None:
            return None
        return "room.bulk:" + str(floor_id) + ":" + hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint(floor_id: UUID, data: s.RoomBulkCreate) -> str:
        canonical = {"floor_id": str(floor_id), "rooms": [r.model_dump(mode="json") for r in data.rooms]}
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _replay(self, key: str, fingerprint: str):
        event = repo.outbox_by_dedupe(self.session, key)
        if event is None:
            return None
        batch = event.payload.get("_batch")
        if not isinstance(batch, dict) or batch.get("fingerprint") != fingerprint:
            raise conflict("Idempotency-Key was already used for a different request")
        ids = [UUID(item) for item in batch["room_ids"]]
        rooms = [self.need(m.Room, item) for item in ids]
        return rooms

    def create_rooms(self, floor_id: UUID, data: s.RoomBulkCreate,
                     idempotency_key: str | None = None, correlation_id: UUID | None = None):
        key = self._idempotency_key(floor_id, idempotency_key)
        fingerprint = self._fingerprint(floor_id, data)
        try:
            with self.atomic():
                if key is not None:
                    replay = self._replay(key, fingerprint)
                    if replay is not None:
                        return replay
                floor, building, prop = self._floor_lineage(floor_id)
                for item in data.rooms:
                    if item.property_id is not None and item.property_id != prop.id:
                        raise conflict("Floor does not belong to requested property")
                codes = [item.room_code for item in data.rooms]
                if repo.code_exists(self.session, prop.id, codes):
                    raise conflict("room_code already exists in this property")
                now = datetime.now(timezone.utc)
                trace = correlation_id or uuid4()
                rows = []
                for item in data.rooms:
                    row = m.Room(id=uuid4(), property_id=prop.id, floor_id=floor.id,
                                 room_code=item.room_code, area_m2=item.area_m2,
                                 listed_rent=item.listed_rent, status="ACTIVE")
                    repo.add(self.session, row)
                    rows.append(row)
                ids = [str(row.id) for row in rows]
                for index, row in enumerate(rows):
                    event_id = uuid4()
                    envelope = {
                        "event_id": str(event_id), "event_type": "RoomCreated", "event_version": 1,
                        "occurred_at": now.isoformat(), "correlation_id": str(trace),
                        "aggregate_id": str(row.id),
                        "data": {"room_id": str(row.id), "property_id": str(row.property_id),
                                 "floor_id": str(row.floor_id), "room_code": row.room_code},
                    }
                    if key is not None and index == 0:
                        envelope["_batch"] = {"fingerprint": fingerprint, "room_ids": ids}
                    repo.add(self.session, m.OutboxEvent(
                        id=event_id, aggregate_type="Room", aggregate_id=row.id,
                        event_type="RoomCreated", event_version=1, payload=envelope,
                        correlation_id=trace, dedupe_key=key if key is not None and index == 0
                        else f"room.created.v1:{row.id}",
                    ))
            return rows
        except RoomError as err:
            # A racing retry may lose the unique outbox key; re-read after rollback.
            if key is not None and err.code == "CONFLICT" and err.message == "Database constraint violation":
                replay = self._replay(key, fingerprint)
                if replay is not None:
                    return replay
            raise

    def patch_room(self, room_id: UUID, data: s.RoomPatch):
        with self.atomic():
            row = self.need(m.Room, room_id, lock=True)
            fields = data.model_dump(exclude_unset=True)
            if fields.get("status") == "INACTIVE" and row.status == "ACTIVE":
                if row.occupancy_contract_id is not None:
                    raise conflict("Cannot deactivate occupied room")
            if fields.get("status") == "ACTIVE" and row.status != "ACTIVE":
                self._floor_lineage(row.floor_id)
            if "room_code" in fields and repo.code_exists(self.session, row.property_id, [fields["room_code"]], exclude_id=room_id):
                raise conflict("room_code already exists in this property")
            for field, value in fields.items():
                setattr(row, field, value)
            self.session.flush()
        return row

    def deactivate(self, kind: str, object_id: UUID):
        mapping = {"property": (m.Property, s.PropertyPatch),
                   "building": (m.Building, s.BuildingPatch),
                   "floor": (m.Floor, s.FloorPatch),
                   "room": (m.Room, s.RoomPatch)}
        model, patch = mapping[kind]
        getattr(self, f"patch_{kind}")(object_id, patch(status="INACTIVE"))

    def validate_room(self, room_id: UUID) -> s.RoomValidation:
        room = repo.get(self.session, m.Room, room_id)
        if room is None:
            return s.RoomValidation(room_id=room_id, exists=False, operational=False)
        floor = repo.get(self.session, m.Floor, room.floor_id)
        building = repo.get(self.session, m.Building, floor.building_id) if floor else None
        prop = repo.get(self.session, m.Property, building.property_id) if building else None
        operational = all(x is not None and x.status == "ACTIVE" for x in (room, floor, building, prop))
        return s.RoomValidation(room_id=room_id, exists=True, operational=operational,
                                property_id=room.property_id, room_code=room.room_code)

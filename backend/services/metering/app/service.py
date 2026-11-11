"""Handle RoomCreated exactly once as a business effect (at-least-once delivery)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.orm import Session

from app import repository as repo


class RoomCreatedData(BaseModel):
    room_id: UUID
    property_id: UUID
    floor_id: UUID
    room_code: str


class RoomCreatedEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_id: UUID
    event_type: Literal["RoomCreated"]
    event_version: Literal[1]
    occurred_at: datetime
    correlation_id: UUID
    aggregate_id: UUID
    data: RoomCreatedData

    @model_validator(mode="after")
    def matching_aggregate(self):
        if self.aggregate_id != self.data.room_id:
            raise ValueError("RoomCreated aggregate_id must equal data.room_id")
        return self


class MeteringService:
    def __init__(self, session: Session):
        self.session = session

    @contextmanager
    def atomic(self):
        tx = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        with tx:
            yield

    def process_room_created(self, raw: dict) -> bool:
        """True if this event ID was new. Creates exactly ELECTRICITY and WATER.

        Atomic: processed_events row and both meters commit (or roll back) together.
        PostgreSQL unique constraints protect against concurrent duplicate events,
        including distinct event IDs for the same room.
        """
        event = RoomCreatedEnvelope.model_validate(raw)
        with self.atomic():
            inserted = repo.mark_processed(self.session, event.event_id, event.event_type)
            if inserted:
                repo.ensure_meter(self.session, event.data.room_id, "ELECTRICITY")
                repo.ensure_meter(self.session, event.data.room_id, "WATER")
        return inserted

    def meters_for_room(self, room_id: UUID):
        return repo.meters_for_room(self.session, room_id)

    def list_meters(self, status: str | None = "ACTIVE", page: int = 1, page_size: int = 100):
        return repo.list_meters(self.session, status=status, page=page, page_size=page_size)

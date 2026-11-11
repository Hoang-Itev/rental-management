"""Metering database operations only. No cross-database FK or explicit commits."""
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app import models as m


def _insert(session: Session, entity):
    # SQLite is used only for fast unit tests; the deployed DB is PostgreSQL.
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(entity)
    return pg_insert(entity)


def mark_processed(session: Session, event_id: UUID, event_type: str) -> bool:
    statement = (
        _insert(session, m.ProcessedEvent)
        .values(event_id=event_id, event_type=event_type)
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(m.ProcessedEvent.event_id)
    )
    return session.scalar(statement) is not None


def ensure_meter(session: Session, room_id: UUID, meter_type: str) -> None:
    unit = "KWH" if meter_type == "ELECTRICITY" else "M3"
    # Deterministic code and DB uniqueness (room_id, meter_type).
    code = ("E-" if meter_type == "ELECTRICITY" else "W-") + room_id.hex
    statement = (
        _insert(session, m.Meter)
        .values(id=uuid4(), room_id=room_id, meter_code=code,
                meter_type=meter_type, unit=unit, initial_reading=0, status="ACTIVE")
        .on_conflict_do_nothing(index_elements=["room_id", "meter_type"])
    )
    session.execute(statement)


def meters_for_room(session: Session, room_id: UUID):
    return list(session.scalars(select(m.Meter).where(m.Meter.room_id == room_id).order_by(m.Meter.meter_type)))


def list_meters(session: Session, status: str | None = "ACTIVE", page: int = 1, page_size: int = 100):
    where = (m.Meter.status == status,) if status is not None else ()
    stmt = select(m.Meter).where(*where).order_by(m.Meter.room_id, m.Meter.meter_type)
    rows = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    total = session.scalar(select(func.count()).select_from(m.Meter).where(*where))
    return list(rows), int(total or 0)

"""SQLAlchemy queries confined to room_db; NO commit in repository helpers."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as m


def get(session: Session, model, object_id: UUID, *, lock: bool = False):
    return session.get(model, object_id, with_for_update=lock)


def page(session: Session, model, *, page_number: int, page_size: int, filters=(), order_by=None):
    criteria = tuple(filters)
    query = select(model).where(*criteria)
    if order_by is None:
        order_by = model.id
    rows = session.scalars(query.order_by(order_by, model.id).offset((page_number - 1) * page_size).limit(page_size)).all()
    total = session.scalar(select(func.count()).select_from(model).where(*criteria))
    return list(rows), int(total or 0)


def any_active(session: Session, model, field, parent_id: UUID) -> bool:
    return session.scalar(select(model.id).where(field == parent_id, model.status == "ACTIVE").limit(1)) is not None


def code_exists(session: Session, property_id: UUID, codes: list[str], exclude_id: UUID | None = None) -> bool:
    query = select(m.Room.id).where(m.Room.property_id == property_id, func.upper(m.Room.room_code).in_(codes))
    if exclude_id is not None:
        query = query.where(m.Room.id != exclude_id)
    return session.scalar(query.limit(1)) is not None


def outbox_by_dedupe(session: Session, dedupe_key: str):
    return session.scalar(select(m.OutboxEvent).where(m.OutboxEvent.dedupe_key == dedupe_key))


def add(session: Session, item):
    session.add(item)
    session.flush()  # Detect database UNIQUE/FK/trigger violations before returning.
    return item


def claim_room_created_outbox(session: Session):
    """Lock one unpublished RoomCreated row, skipping rows claimed by other workers."""
    query = (
        select(m.OutboxEvent)
        .where(m.OutboxEvent.event_type == "RoomCreated", m.OutboxEvent.published_at.is_(None))
        .order_by(m.OutboxEvent.created_at, m.OutboxEvent.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.scalars(query).first()

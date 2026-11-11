"""Only tenant_db access. No repository method commits a transaction."""
from __future__ import annotations
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import models as m

def get(db: Session, model, object_id: UUID, lock: bool = False):
    return db.get(model, object_id, with_for_update=lock)

def add(db: Session, row):
    db.add(row)
    db.flush()
    return row

def page(db: Session, model, page: int, size: int, conditions=(), order=None):
    conditions=tuple(conditions)
    stmt=select(model).where(*conditions)
    order = order or model.id
    rows=db.scalars(stmt.order_by(order,model.id).offset((page-1)*size).limit(size)).all()
    total=db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    return list(rows), int(total)

def terms(db: Session, contract_id: UUID):
    return list(db.scalars(select(m.ContractTerm).where(m.ContractTerm.contract_id==contract_id)
                           .order_by(m.ContractTerm.effective_from,m.ContractTerm.id)))

def events(db: Session, contract_id: UUID):
    return list(db.scalars(select(m.ContractEvent).where(m.ContractEvent.contract_id==contract_id)
                           .order_by(m.ContractEvent.occurred_at,m.ContractEvent.id)))

def overlapping(db: Session, room_id: UUID, start, end, exclude_contract_id: UUID | None = None):
    stmt=select(m.Contract.id).where(
        m.Contract.room_id==room_id,
        m.Contract.status.in_(('SCHEDULED','ACTIVE','EXPIRED_PENDING')),
        m.Contract.start_date <= end, m.Contract.end_date >= start,
    )
    if exclude_contract_id is not None:
        stmt=stmt.where(m.Contract.id != exclude_contract_id)
    return db.scalar(stmt.limit(1)) is not None


def active_occupant(db: Session, room_id: UUID, exclude_id: UUID) -> bool:
    """Physical occupancy includes overdue contracts after their planned end."""
    return db.scalar(select(m.Contract.id).where(
        m.Contract.room_id == room_id, m.Contract.id != exclude_id,
        m.Contract.status.in_(('ACTIVE', 'EXPIRED_PENDING'))).limit(1)) is not None


def due_contract_ids(db: Session, states: tuple[str, ...]) -> list[UUID]:
    return list(db.scalars(select(m.Contract.id).where(
        m.Contract.status.in_(states)).order_by(m.Contract.start_date, m.Contract.id)))


def actual_occupancy_intersects_start(db: Session, room_id: UUID, start, exclude_id: UUID) -> bool:
    """An ENDED contract may have occupied beyond its planned end_date."""
    return db.scalar(select(m.Contract.id).where(
        m.Contract.room_id == room_id, m.Contract.id != exclude_id,
        m.Contract.status == 'ENDED', m.Contract.actual_end_date.is_not(None),
        m.Contract.start_date <= start, m.Contract.actual_end_date >= start,
    ).limit(1)) is not None

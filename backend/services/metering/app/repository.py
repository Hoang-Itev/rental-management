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


def ensure_handover_cutoffs(session: Session, room_id: UUID, contract_id: UUID,
                            instant, kind: str) -> None:
    """Row-lock each meter; one physical cutoff per meter+instant, two logical reasons."""
    from app import models as m
    for meter_type in ('ELECTRICITY','WATER'):
        ensure_meter(session,room_id,meter_type)
    session.flush()
    meters=list(session.scalars(select(m.Meter).where(m.Meter.room_id==room_id)
                                .order_by(m.Meter.id).with_for_update()))
    if len(meters)!=2:
        raise RuntimeError('Expected exactly two meters')
    reason='CONTRACT_START' if kind=='ContractStarted' else 'CONTRACT_END'
    for meter in meters:
        cutoff=session.scalar(select(m.MeterCutoff).where(
            m.MeterCutoff.meter_id==meter.id, m.MeterCutoff.cutoff_at==instant,
            m.MeterCutoff.status!='SUPERSEDED').with_for_update())
        if cutoff is None:
            cutoff=m.MeterCutoff(id=uuid4(), meter_id=meter.id,
                contract_id=contract_id,cutoff_type=reason, cutoff_at=instant,
                source='AUTOMATIC', status='PENDING')
            session.add(cutoff)
            session.flush()
        elif reason=='CONTRACT_START' and cutoff.cutoff_type=='CONTRACT_END':
            # Stable canonical projection regardless of End(A)/Start(B) arrival order.
            cutoff.cutoff_type='CONTRACT_START'
            cutoff.contract_id=contract_id
            session.flush()
        statement=(_insert(session,m.MeterCutoffReason)
                   .values(id=uuid4(),cutoff_id=cutoff.id,contract_id=contract_id,reason_type=reason)
                   .on_conflict_do_nothing(index_elements=['cutoff_id','contract_id','reason_type']))
        session.execute(statement)

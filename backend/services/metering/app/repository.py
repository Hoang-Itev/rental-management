"""Metering database operations only. No cross-database FK or explicit commits."""
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app import models as m
from app.cutoffs import db_utc


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
        elif reason=='CONTRACT_START' and cutoff.cutoff_type=='CONTRACT_END' and cutoff.status=='PENDING':
            # Stable canonical projection regardless of End(A)/Start(B) arrival order.
            cutoff.cutoff_type='CONTRACT_START'
            cutoff.contract_id=contract_id
            session.flush()
        statement=(_insert(session,m.MeterCutoffReason)
                   .values(id=uuid4(),cutoff_id=cutoff.id,contract_id=contract_id,reason_type=reason)
                   .on_conflict_do_nothing(index_elements=['cutoff_id','contract_id','reason_type']))
        session.execute(statement)


def meter_locked(session: Session, meter_id: UUID):
    """Serialize insert + conflict-alert creation by physical meter."""
    return session.get(m.Meter, meter_id, with_for_update=True)


def reading_at(session: Session, meter_id: UUID, measured_at):
    return session.get(m.MeterReading, (meter_id, measured_at))


def nearest_valid(session: Session, meter_id: UUID, measured_at, *, before: bool):
    stamp = m.MeterReading.measured_at
    criterion = stamp < measured_at if before else stamp > measured_at
    order = stamp.desc() if before else stamp.asc()
    return session.scalar(select(m.MeterReading).where(
        m.MeterReading.meter_id == meter_id,
        m.MeterReading.validation_status == 'VALID', criterion,
    ).order_by(order).limit(1))


def existing_alert(session: Session, meter_id: UUID, measured_at, alert_type: str):
    return session.scalar(select(m.MeterAlert.id).where(
        m.MeterAlert.meter_id == meter_id,
        m.MeterAlert.related_measured_at == measured_at,
        m.MeterAlert.alert_type == alert_type,
    ).limit(1)) is not None


def readings_for_meter(session: Session, meter_id: UUID, *, page=1, page_size=100,
                       from_at=None, to_at=None):
    clauses = [m.MeterReading.meter_id == meter_id]
    if from_at is not None: clauses.append(m.MeterReading.measured_at >= from_at)
    if to_at is not None: clauses.append(m.MeterReading.measured_at <= to_at)
    stmt = select(m.MeterReading).where(*clauses)
    return (list(session.scalars(stmt.order_by(m.MeterReading.measured_at.desc())
                 .limit(page_size).offset((page-1)*page_size))),
            int(session.scalar(select(func.count()).select_from(m.MeterReading)
                .where(*clauses)) or 0))


def alerts_for_meter(session: Session, meter_id: UUID, *, page=1, page_size=100):
    stmt = select(m.MeterAlert).where(m.MeterAlert.meter_id == meter_id)
    return (list(session.scalars(stmt.order_by(m.MeterAlert.detected_at.desc(),m.MeterAlert.id)
                 .limit(page_size).offset((page-1)*page_size))),
            int(session.scalar(select(func.count()).select_from(m.MeterAlert)
                .where(m.MeterAlert.meter_id == meter_id)) or 0))


def list_alerts(session: Session, *, status=None, alert_type=None,
                page=1, page_size=100):
    conditions=[]
    if status:conditions.append(m.MeterAlert.status==status)
    if alert_type:conditions.append(m.MeterAlert.alert_type==alert_type)
    stmt=select(m.MeterAlert).where(*conditions)
    return (list(session.scalars(stmt.order_by(m.MeterAlert.detected_at.desc(),m.MeterAlert.id)
                 .limit(page_size).offset((page-1)*page_size))),
            int(session.scalar(select(func.count()).select_from(m.MeterAlert).where(*conditions)) or 0))


# P07 queries. Selection remains database-side; no cross-service joins.
from datetime import timedelta


def active_cutoff(session: Session, cutoff_id: UUID):
    return session.get(m.MeterCutoff, cutoff_id)


def active_cutoff_at(session: Session, meter_id: UUID, instant, kind: str):
    return session.scalar(select(m.MeterCutoff).where(
        m.MeterCutoff.meter_id == meter_id,
        m.MeterCutoff.cutoff_at == instant,
        m.MeterCutoff.cutoff_type == kind,
        m.MeterCutoff.status != 'SUPERSEDED',
    ).order_by(m.MeterCutoff.id).limit(1))


def closest_valid(session: Session, meter_id: UUID, instant, window: timedelta):
    # Fetch at most two neighbours; do not select SUSPECT/REJECTED or out-of-window.
    stamp = m.MeterReading.measured_at
    base = [m.MeterReading.meter_id == meter_id,
            m.MeterReading.validation_status == 'VALID']
    before = session.scalar(select(m.MeterReading).where(
        *base, stamp >= instant - window, stamp <= instant
    ).order_by(stamp.desc()).limit(1))
    after = session.scalar(select(m.MeterReading).where(
        *base, stamp > instant, stamp <= instant + window
    ).order_by(stamp.asc()).limit(1))
    candidates = [r for r in (before, after) if r is not None]
    return min(candidates, key=lambda r: (
        abs(db_utc(r.measured_at) - instant), db_utc(r.measured_at) > instant
    )) if candidates else None


def pending_cutoff_ids(session: Session, until):
    return list(session.scalars(select(m.MeterCutoff.id).where(
        m.MeterCutoff.status == 'PENDING', m.MeterCutoff.cutoff_at <= until
    ).order_by(m.MeterCutoff.cutoff_at, m.MeterCutoff.id)))


def list_cutoffs(session: Session, *, meter_id=None, room_id=None, status=None,
                 cutoff_type=None, from_at=None, to_at=None, page=1, page_size=100):
    filters = []
    if meter_id is not None: filters.append(m.MeterCutoff.meter_id == meter_id)
    if room_id is not None: filters.append(m.Meter.room_id == room_id)
    if status is not None: filters.append(m.MeterCutoff.status == status)
    if cutoff_type is not None: filters.append(m.MeterCutoff.cutoff_type == cutoff_type)
    if from_at is not None: filters.append(m.MeterCutoff.cutoff_at >= from_at)
    if to_at is not None: filters.append(m.MeterCutoff.cutoff_at < to_at)  # exclusive
    stmt = select(m.MeterCutoff).join(m.Meter).where(*filters)
    count = select(func.count()).select_from(m.MeterCutoff).join(m.Meter).where(*filters)
    rows = session.scalars(stmt.order_by(m.MeterCutoff.cutoff_at.desc(),
        m.MeterCutoff.created_at.desc(),m.MeterCutoff.id)
        .offset((page-1)*page_size).limit(page_size)).all()
    return list(rows), int(session.scalar(count) or 0)


def cutoff_reasons(session: Session, cutoff_id: UUID):
    return list(session.scalars(select(m.MeterCutoffReason).where(
        m.MeterCutoffReason.cutoff_id == cutoff_id)))


def open_offline(session: Session, meter_id: UUID):
    return session.scalar(select(m.MeterAlert).where(
        m.MeterAlert.meter_id == meter_id,
        m.MeterAlert.alert_type == 'OFFLINE',
        m.MeterAlert.status == 'OPEN',
    ).limit(1))


def resolve_offline(session: Session, meter_id: UUID, now):
    alert = open_offline(session, meter_id)
    if alert is not None:
        alert.status = 'RESOLVED'
        alert.resolved_at = now
        alert.resolution_note = 'Telemetry received'
    return alert is not None


def alert_for_cutoff(session: Session, cutoff_id: UUID, meter_id: UUID, kind: str):
    return session.scalar(select(m.MeterAlert).where(
        m.MeterAlert.meter_id == meter_id,
        m.MeterAlert.related_cutoff_id == cutoff_id,
        m.MeterAlert.alert_type == kind,
        m.MeterAlert.status == 'OPEN',
    ).limit(1))


def latest_valid_reading(session: Session, meter_id: UUID):
    return session.scalar(select(m.MeterReading).where(
        m.MeterReading.meter_id == meter_id,
        m.MeterReading.validation_status == 'VALID',
    ).order_by(m.MeterReading.measured_at.desc()).limit(1))


def active_cutoff_at_any_type(session: Session, meter_id: UUID, instant):
    """One physical cutoff per meter+instant (handover/monthly may share it)."""
    return session.scalar(select(m.MeterCutoff).where(
        m.MeterCutoff.meter_id == meter_id,
        m.MeterCutoff.cutoff_at == instant,
        m.MeterCutoff.status != 'SUPERSEDED',
    ).order_by(m.MeterCutoff.id).limit(1))


def current_confirmed_near_reading(session: Session, meter_id: UUID, measured_at, window: timedelta):
    return list(session.scalars(select(m.MeterCutoff).where(
        m.MeterCutoff.meter_id == meter_id,
        m.MeterCutoff.status == 'CONFIRMED',
        m.MeterCutoff.source == 'AUTOMATIC',
        m.MeterCutoff.cutoff_at >= measured_at - window,
        m.MeterCutoff.cutoff_at <= measured_at + window,
    )))


def active_cutoff_times(session: Session, meter_id: UUID, from_at, to_at):
    rows = session.scalars(select(m.MeterCutoff.cutoff_at).where(
        m.MeterCutoff.meter_id == meter_id,
        m.MeterCutoff.cutoff_at >= from_at,
        m.MeterCutoff.cutoff_at <= to_at,
        m.MeterCutoff.status != 'SUPERSEDED',
    )).all()
    return {db_utc(stamp) for stamp in rows}

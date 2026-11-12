"""Lifecycle scheduler; physical occupancy is never released by EXPIRED_PENDING.

Run as python -m app.scheduler. Explicit job endpoint shares run_due().
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import String, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker
from app import models as m, repository as repo
from app.clients import RoomClient
from app.config import get_settings
from app.db import get_sessionmaker
from app.service import TenantError, TenantService, VN

logger=logging.getLogger(__name__)


def run_due(*, now: datetime | None = None, sessions: sessionmaker[Session] | None = None,
            room_factory=None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Scheduler time must be timezone-aware')
    sessions = sessions or get_sessionmaker()
    room_factory = room_factory or (lambda: RoomClient(get_settings()))
    with sessions() as db:
        expiring = repo.due_contract_ids(db, ('ACTIVE',))
        scheduled = repo.due_contract_ids(db, ('SCHEDULED',))
        handovers = repo.pending_handover_ids(db)
    count, started, pending = 0, 0, 0
    
    from app.service import _boundary, _end_exclusive

    # Complete recorded handovers before processing expiry or activation.
    for cid, end_day, reason in handovers:
        if now < _boundary(_end_exclusive(end_day)):
            continue

        try:
            with sessions() as db:
                TenantService(db, room_factory()).end_contract(
                    cid, end_day, reason, now=now
                )
            count += 1
        except TenantError as exc:
            if exc.status != 409:
                raise

    # Expiry must run before activation for predictable transition ordering.
    for cid in expiring:
        try:
            with sessions() as db:
                TenantService(db, room_factory()).mark_expired(cid, now=now)
            pending += 1
        except TenantError as exc:
            if exc.status != 409:
                raise
        count += 1
    for cid in scheduled:
        try:
            with sessions() as db:
                TenantService(db, room_factory()).activate(cid, now=now)
            started += 1
        except TenantError as exc:
            if exc.status != 409:
                raise
            logger.info('Deferred scheduled contract %s: %s', cid, exc.message)
        count += 1
    return {'job_id': uuid4(), 'processed': count, 'started': started, 'pending_end': pending}


def enqueue_expiring_contracts(sessions, now=None, days=7):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(VN)
    if local.hour < 9:
        return 0
    today = local.date()
    already_enqueued = select(m.OutboxEvent.id).where(
        m.OutboxEvent.dedupe_key == func.concat("contract.expiring.v1:", cast(m.Contract.id, String),
                                                ":", func.to_char(m.Contract.end_date, "YYYY-MM-DD")),
    ).exists()
    with sessions.begin() as db:
        rows = db.execute(select(m.Contract, m.Tenant.full_name).join(m.Contract.representative).where(
            m.Contract.status == "ACTIVE", m.Contract.actual_end_date.is_(None),
            m.Contract.end_date.between(today, today + timedelta(days=days)),
            ~already_enqueued,
        ).order_by(m.Contract.end_date, m.Contract.id).limit(100)
          .with_for_update(of=m.Contract, skip_locked=True)).all()
        count = 0
        for contract, name in rows:
            event_id = uuid4()
            result = db.execute(insert(m.OutboxEvent).values(
                id=event_id, aggregate_type="Contract", aggregate_id=contract.id,
                event_type="ContractExpiring", event_version=1, correlation_id=event_id,
                dedupe_key=f"contract.expiring.v1:{contract.id}:{contract.end_date.isoformat()}",
                payload={
                    "event_id": str(event_id), "event_type": "ContractExpiring", "event_version": 1,
                    "occurred_at": now.isoformat(), "effective_at": now.isoformat(),
                    "aggregate_id": str(contract.id), "correlation_id": str(event_id),
                    "data": {
                        "contract_id": str(contract.id), "room_id": str(contract.room_id),
                        "end_date": contract.end_date.isoformat(), "days_remaining": (contract.end_date - today).days,
                        "room_code": contract.room_code_snapshot, "tenant_name": name,
                    },
                },
            ).on_conflict_do_nothing(index_elements=[m.OutboxEvent.dedupe_key]).returning(m.OutboxEvent.id))
            count += result.scalar_one_or_none() is not None
        return count


def main():
    logging.basicConfig(level='INFO')
    while True:
        try:
            run_due()
        except Exception as exc:
            logger.exception('Contract lifecycle poll failed: %s', type(exc).__name__)
        try:
            enqueue_expiring_contracts(get_sessionmaker())
        except Exception as exc:
            logger.exception('Contract expiry notification poll failed: %s', type(exc).__name__)
        time.sleep(30)


if __name__ == '__main__':
    main()

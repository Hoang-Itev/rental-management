"""Lifecycle scheduler; physical occupancy is never released by EXPIRED_PENDING.

Run as python -m app.scheduler. Explicit job endpoint shares run_due().
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session, sessionmaker
from app import repository as repo
from app.clients import RoomClient
from app.config import get_settings
from app.db import get_sessionmaker
from app.service import TenantError, TenantService

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


def main():
    logging.basicConfig(level='INFO')
    while True:
        try:
            run_due()
        except Exception as exc:
            logger.exception('Contract lifecycle poll failed: %s', type(exc).__name__)
        time.sleep(30)


if __name__ == '__main__':
    main()

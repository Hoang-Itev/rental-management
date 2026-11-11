"""P07 cutoff scheduler: idempotent monthly boundaries, selection and offline scan.

Run `python -m app.scheduler --once` for manual validation, or without flag
for a long-running Docker worker. Do not run this in the HTTP process.
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session, sessionmaker
from app.db import get_sessionmaker
from app.service import MeteringService

logger = logging.getLogger('metering.cutoffs.scheduler')


def run_due(*, now: datetime | None = None,
            sessions: sessionmaker[Session] | None = None,
            offline_minutes: int = 20, months_back: int = 24) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must include timezone')
    sessions = sessions or get_sessionmaker()
    with sessions() as db:
        return MeteringService(db).run_cutoff_jobs(
            now=now, offline_minutes=offline_minutes, months_back=months_back)


def main() -> None:
    parser = argparse.ArgumentParser(description='P07 idempotent meter cutoff scheduler')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    interval = int(os.getenv('P07_JOB_INTERVAL_SECONDS', '60'))
    offline = int(os.getenv('P07_OFFLINE_MINUTES', '20'))
    months = int(os.getenv('P07_MONTHS_BACK', '24'))
    if interval < 5:
        raise ValueError('P07_JOB_INTERVAL_SECONDS must be >=5')
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            logger.info('P07 cutoff job: %s', run_due(offline_minutes=offline, months_back=months))
        except Exception:
            logger.exception('P07 cutoff job failed')
            if args.once:
                raise
        if args.once:
            return
        time.sleep(interval)


if __name__ == '__main__':
    main()

"""Consume durable billing jobs and retry waiting invoices."""
import logging
from datetime import datetime, timedelta
from threading import Event
import signal

import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.clients import BillingClients, DependencyUnavailable
from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.models import BillingRun, Invoice
from app.service import InvoiceConflict, InvoiceService, VN

logger = logging.getLogger("billing.scheduler")
LOCK = "hashtextextended('rental-management:billing:scheduler', 0)"


def last_due_month(now: datetime):
    local = now.astimezone(VN)
    first = local.date().replace(day=1)
    if local.day == 1 and local.hour < 2:
        first = (first - timedelta(days=1)).replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


def tick(engine, service, now):
    # A dedicated connection owns the lock until all work for this tick is done.
    with engine.connect() as lock_connection:
        acquired = lock_connection.scalar(text(f"SELECT pg_try_advisory_lock({LOCK})"))
        lock_connection.commit()
        if not acquired:
            return
        try:
            run_month = last_due_month(now)
            service.enqueue_month(run_month, "SCHEDULED", run_month.isoformat())
            with service.sessions() as db:
                drafts = db.execute(select(Invoice.id, Invoice.contract_id, Invoice.billing_month).where(
                    Invoice.status == "DRAFT", Invoice.invoice_type == "PERIODIC",
                    Invoice.billing_month <= run_month,
                )).all()
                jobs = db.scalars(select(BillingRun.id).where(BillingRun.status == "RUNNING")
                                  .order_by(BillingRun.started_at, BillingRun.id)).all()
            for job_id in jobs:
                service.execute_run(job_id)
            for invoice_id, contract_id, month in drafts:
                try:
                    service.process(contract_id, month, expected_id=invoice_id)
                except (DependencyUnavailable, IntegrityError):
                    logger.warning("Could not retry invoice %s", invoice_id)
                except InvoiceConflict:
                    # A concurrent manual action changed the active invoice.
                    continue
        finally:
            try:
                lock_connection.execute(text(f"SELECT pg_advisory_unlock({LOCK})"))
            except Exception:
                lock_connection.invalidate()
                raise


def run():
    settings = get_settings()
    stop = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    with httpx.Client(timeout=settings.billing_http_timeout_seconds, trust_env=False) as http:
        service = InvoiceService(get_sessionmaker(), BillingClients(http, settings))
        while not stop.is_set():
            try:
                tick(get_engine(), service, datetime.now(VN))
            except Exception:
                logger.exception("Billing scheduler tick failed")
            stop.wait(settings.billing_poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

"""Create one overdue reminder per invoice and Vietnam calendar day."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, cast, func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import Invoice, OutboxEvent
from app.service import LinkDenied, VN


def reminder_reason(invoice, today):
    if invoice.status == "PAID":
        return "ALREADY_PAID"
    if invoice.status == "VOID":
        return "VOID"
    if invoice.status != "ISSUED":
        return "NOT_ISSUED"
    if invoice.due_date >= today or invoice.total_amount <= 0:
        return "NOT_DUE"
    return "OUTSTANDING"


def enqueue_reminder(db, invoice, now):
    today = now.astimezone(VN).date()
    if reminder_reason(invoice, today) != "OUTSTANDING" or not invoice.tenant_email_snapshot:
        raise LinkDenied(409, "INVOICE_NOT_REMINDABLE")
    event_id = uuid4()
    kind = "InvoiceReminderRequested"
    result = db.execute(insert(OutboxEvent).values(
        id=event_id, aggregate_type="Invoice", aggregate_id=invoice.id, event_type=kind,
        event_version=1, correlation_id=event_id,
        dedupe_key=f"invoice.reminder_requested.v1:{invoice.id}:{today.isoformat()}",
        payload={
            "event_id": str(event_id), "event_type": kind, "event_version": 1,
            "occurred_at": now.isoformat(), "correlation_id": str(event_id), "aggregate_id": str(invoice.id),
            "data": {
                "invoice_id": str(invoice.id), "recipient_email": invoice.tenant_email_snapshot,
                "reminder_date": today.isoformat(), "due_date": invoice.due_date.isoformat(),
                "invoice_code": invoice.invoice_code, "total_amount": invoice.total_amount,
                "tenant_name": invoice.tenant_name_snapshot, "room_code": invoice.room_code_snapshot,
                "period_start": invoice.period_start.isoformat(), "period_end_exclusive": invoice.period_end.isoformat(),
            },
        },
    ).on_conflict_do_nothing(index_elements=[OutboxEvent.dedupe_key]).returning(OutboxEvent.id))
    return result.scalar_one_or_none() is not None


def enqueue_daily_reminders(sessions, now=None):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(VN)
    if local.hour < 9:
        return 0
    today = local.date()
    already_enqueued = select(OutboxEvent.id).where(
        OutboxEvent.dedupe_key == func.concat("invoice.reminder_requested.v1:",
                                              cast(Invoice.id, String), ":", today.isoformat()),
    ).exists()
    with sessions.begin() as db:
        invoices = db.scalars(select(Invoice).where(
            Invoice.status == "ISSUED", Invoice.due_date < today, Invoice.total_amount > 0,
            Invoice.tenant_email_snapshot.is_not(None), Invoice.tenant_email_snapshot != "",
            ~already_enqueued,
        ).order_by(Invoice.due_date, Invoice.id).limit(100).with_for_update(skip_locked=True)).all()
        return sum(enqueue_reminder(db, invoice, now) for invoice in invoices)

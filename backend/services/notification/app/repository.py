from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.models import EmailJob


def insert_once(db, event, subject, *, email_type="INVOICE", recipient=None, skipped=False):
    data = event.data
    statement = insert(EmailJob).values(
        source_event_id=event.event_id, invoice_id=getattr(data, "invoice_id", None),
        email_type=email_type, recipient_email=recipient or data.recipient_email, subject=subject,
        status="SKIPPED" if skipped else "PENDING", last_error="ALREADY_PAID" if skipped else None,
        template_data=data.model_dump(mode="json", exclude={"recipient_email"}),
    ).on_conflict_do_nothing(index_elements=[EmailJob.source_event_id])
    db.execute(statement)



def lock_invoice_events(db, invoice_id):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
               {"key": f"notification-invoice:{invoice_id}"})


def has_payment_receipt(db, invoice_id):
    return db.scalar(select(EmailJob.id).where(
        EmailJob.invoice_id == invoice_id, EmailJob.email_type == "PAYMENT_RECEIPT",
    ).limit(1)) is not None


def skip_pending_reminders(db, invoice_id):
    db.execute(update(EmailJob).where(
        EmailJob.invoice_id == invoice_id, EmailJob.email_type == "REMINDER",
        EmailJob.status == "PENDING",
    ).values(status="SKIPPED", last_error="ALREADY_PAID", next_attempt_at=None))


def claim_due(db, now):
    return db.scalar(select(EmailJob).where(
        EmailJob.status == "PENDING",
        or_(EmailJob.next_attempt_at.is_(None), EmailJob.next_attempt_at <= now),
    ).order_by(EmailJob.created_at, EmailJob.id).limit(1).with_for_update(skip_locked=True))


def page(db, conditions, number, size):
    query = select(EmailJob).where(*conditions)
    return {
        "items": db.scalars(query.order_by(EmailJob.created_at.desc(), EmailJob.id)
                            .offset((number - 1) * size).limit(size)).all(),
        "meta": {"page": number, "page_size": size,
                 "total": db.scalar(select(func.count()).select_from(EmailJob).where(*conditions))},
    }

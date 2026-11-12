from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.models import EmailJob


def insert_once(db, event, subject):
    data = event.data
    statement = insert(EmailJob).values(
        source_event_id=event.event_id, invoice_id=data.invoice_id,
        email_type="INVOICE", recipient_email=data.recipient_email, subject=subject,
        template_data=data.model_dump(mode="json", exclude={"recipient_email"}),
    ).on_conflict_do_nothing(index_elements=[EmailJob.source_event_id])
    db.execute(statement)


def claim_due(db, now):
    return db.scalar(select(EmailJob).where(
        EmailJob.email_type == "INVOICE", EmailJob.status == "PENDING",
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

"""Queries for Billing-owned tables."""
from sqlalchemy import func, select, text

from app.models import BillingRun, Invoice, OutboxEvent


def lock_contract(db, contract_id):
    # Also protects the first insertion, when no invoice row exists to lock.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
               {"key": f"billing-invoice:{contract_id}"})


def periodic_invoice(db, contract_id, month):
    return db.scalar(select(Invoice).where(
        Invoice.contract_id == contract_id, Invoice.billing_month == month,
        Invoice.invoice_type == "PERIODIC", Invoice.status != "VOID",
    ).with_for_update())


def page(db, model, conditions, page_number, size):
    query = select(model).where(*conditions)
    order = BillingRun.started_at if model is BillingRun else model.created_at
    rows = db.scalars(query.order_by(order.desc(), model.id).offset((page_number - 1) * size).limit(size)).all()
    count = db.scalar(select(func.count()).select_from(model).where(*conditions))
    return {"items": rows, "meta": {"page": page_number, "page_size": size, "total": count}}


def claim_outbox(db):
    return db.scalar(select(OutboxEvent).where(
        OutboxEvent.event_type.in_(("InvoiceIssued", "PaymentSucceeded", "InvoiceReminderRequested")), OutboxEvent.published_at.is_(None),
    ).order_by(OutboxEvent.attempts, OutboxEvent.created_at, OutboxEvent.id).limit(1).with_for_update(skip_locked=True))


def usable_invoice_link(db, token_hash, now):
    from app.models import InvoiceAccessToken

    return db.scalar(select(InvoiceAccessToken).join(InvoiceAccessToken.invoice).where(
        InvoiceAccessToken.token_hash == token_hash,
        InvoiceAccessToken.revoked_at.is_(None),
        InvoiceAccessToken.expires_at > now,
        Invoice.status.in_(("ISSUED", "PAID")),
    ))


def payment_attempt(db, invoice_id, *, status=None, request_id=None):
    from app.models import PaymentAttempt

    filters = [PaymentAttempt.invoice_id == invoice_id]
    if status is not None:
        filters.append(PaymentAttempt.status == status)
    if request_id is not None:
        filters.append(PaymentAttempt.request_id == request_id)
    return db.scalar(select(PaymentAttempt).where(*filters).with_for_update())


def payment_candidates(db, cutoff, limit, attempt_id=None):
    from app.models import PaymentAttempt, PaymentWebhookReceipt
    from sqlalchemy import or_

    flagged = select(PaymentWebhookReceipt.id).where(
        PaymentWebhookReceipt.payment_attempt_id == PaymentAttempt.id,
        PaymentWebhookReceipt.processing_result == "RECONCILIATION_REQUIRED",
    ).exists()
    query = select(PaymentAttempt.id).where(
        PaymentAttempt.provider == "MOMO",
        or_(PaymentAttempt.status == "PENDING", flagged),
    )
    if attempt_id is None:
        query = query.where(PaymentAttempt.created_at <= cutoff,
                            or_(PaymentAttempt.last_reconciled_at.is_(None),
                                PaymentAttempt.last_reconciled_at <= cutoff))
    else:
        query = query.where(PaymentAttempt.id == attempt_id)
    return db.scalars(query.order_by(PaymentAttempt.last_reconciled_at.asc().nulls_first(),
                                    PaymentAttempt.created_at, PaymentAttempt.id).limit(limit)).all()


def final_invoice(db, contract_id):
    return db.scalar(select(Invoice).where(
        Invoice.contract_id == contract_id, Invoice.invoice_type == "FINAL", Invoice.status != "VOID",
    ).with_for_update())


def covered_periods(db, contract_id, start, end, exclude_id=None):
    query = select(Invoice.period_start, Invoice.period_end).where(
        Invoice.contract_id == contract_id, Invoice.status != "VOID",
        Invoice.period_start < end, Invoice.period_end > start,
    )
    if exclude_id is not None:
        query = query.where(Invoice.id != exclude_id)
    return db.execute(query).all()


def periodic_was_voided(db, contract_id, month):
    return db.scalar(select(Invoice.id).where(
        Invoice.contract_id == contract_id, Invoice.billing_month == month,
        Invoice.invoice_type == "PERIODIC", Invoice.status == "VOID",
    ).limit(1)) is not None


def revoke_invoice_tokens(db, invoice_id, now):
    from sqlalchemy import update
    from app.models import InvoiceAccessToken

    db.execute(update(InvoiceAccessToken).where(
        InvoiceAccessToken.invoice_id == invoice_id, InvoiceAccessToken.revoked_at.is_(None),
    ).values(revoked_at=now))

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
    order = Invoice.created_at if model is Invoice else BillingRun.started_at
    rows = db.scalars(query.order_by(order.desc(), model.id).offset((page_number - 1) * size).limit(size)).all()
    count = db.scalar(select(func.count()).select_from(model).where(*conditions))
    return {"items": rows, "meta": {"page": page_number, "page_size": size, "total": count}}


def claim_outbox(db):
    return db.scalar(select(OutboxEvent).where(
        OutboxEvent.event_type == "InvoiceIssued", OutboxEvent.published_at.is_(None),
    ).order_by(OutboxEvent.attempts, OutboxEvent.created_at, OutboxEvent.id).limit(1).with_for_update(skip_locked=True))

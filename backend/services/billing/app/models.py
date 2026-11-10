"""Database Design V3: ORM models belonging ONLY to this service database.

Do not add cross-database ForeignKey or import ORM models of other services.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index, text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UUIDPK:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class AuditTimes:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def status_check(name: str, column: str, *values: str) -> CheckConstraint:
    enum_values = ", ".join("'" + v + "'" for v in values)
    return CheckConstraint(f"{column} IN ({enum_values})", name=name)

class Invoice(UUIDPK, AuditTimes, Base):
    __tablename__ = "invoices"
    invoice_code: Mapped[str] = mapped_column(sa.String(80), nullable=False, unique=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # Tenant logical ref
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # Room logical ref
    invoice_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    billing_month: Mapped[date | None] = mapped_column(sa.Date)
    period_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    period_end: Mapped[date] = mapped_column(sa.Date, nullable=False)  # exclusive
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="DRAFT")
    blocked_reason: Mapped[str | None] = mapped_column(sa.Text)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    replaces_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    void_reason: Mapped[str | None] = mapped_column(sa.Text)
    total_amount: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, server_default="0")
    due_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    tenant_name_snapshot: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    tenant_email_snapshot: Mapped[str | None] = mapped_column(sa.String(254))
    room_code_snapshot: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice")
    attempts: Mapped[list[PaymentAttempt]] = relationship(back_populates="invoice")
    tokens: Mapped[list[InvoiceAccessToken]] = relationship(back_populates="invoice")
    adjustments: Mapped[list[InvoiceAdjustment]] = relationship(back_populates="invoice")
    __table_args__ = (
        status_check("invoice_type_values", "invoice_type", "PERIODIC", "FINAL"),
        status_check("status_values", "status", "DRAFT", "ISSUED", "PAID", "VOID"),
        CheckConstraint("period_end > period_start", name="period_order"),
        CheckConstraint("total_amount >= 0", name="total_nonnegative"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("invoice_type <> 'PERIODIC' OR billing_month IS NOT NULL", name="periodic_has_month"),
        ExcludeConstraint(
            ("contract_id", "="),
            (text("daterange(period_start, period_end, '[)')"), "&&"),
            name="ex_invoices_contract_period",
            where=text("status <> 'VOID'"),
            using="gist",
        ),
        Index("uq_invoices_month_live", "contract_id", "billing_month", unique=True, postgresql_where=text("invoice_type = 'PERIODIC' AND status <> 'VOID'")),
        Index("uq_invoices_final_live", "contract_id", unique=True, postgresql_where=text("invoice_type = 'FINAL' AND status <> 'VOID'")),
        Index("ix_invoices_status_due", "status", "due_date"),
        Index("ix_invoices_contract_month", "contract_id", "billing_month"),
    )


class InvoiceItem(UUIDPK, Base):
    __tablename__ = "invoice_items"
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    amount: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    period_start: Mapped[date | None] = mapped_column(sa.Date)
    period_end: Mapped[date | None] = mapped_column(sa.Date)
    meter_start_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(16, 3))
    meter_end_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(16, 3))
    source_term_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Tenant logical ref
    source_cutoff_start_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Metering ref
    source_cutoff_end_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Metering ref
    invoice: Mapped[Invoice] = relationship(back_populates="items")
    __table_args__ = (
        status_check("item_type_values", "item_type", "RENT", "ELECTRICITY", "WATER", "SERVICE"),
        CheckConstraint("quantity >= 0 AND unit_price >= 0 AND amount >= 0", name="price_nonnegative"),
        CheckConstraint("period_start IS NULL OR period_end IS NULL OR period_end > period_start", name="item_period_valid"),
    )


class InvoiceAdjustment(UUIDPK, Base):
    __tablename__ = "invoice_adjustments"
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    amount_delta: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="OPEN")
    resolution_note: Mapped[str | None] = mapped_column(sa.Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Auth logical ref
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    invoice: Mapped[Invoice] = relationship(back_populates="adjustments")
    __table_args__ = (status_check("status_values", "status", "OPEN", "RESOLVED", "REJECTED"),)


class PaymentAttempt(UUIDPK, AuditTimes, Base):
    __tablename__ = "payment_attempts"
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    provider: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    order_id: Mapped[str] = mapped_column(sa.String(120), nullable=False, unique=True)
    request_id: Mapped[str] = mapped_column(sa.String(120), nullable=False, unique=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(sa.String(120))
    amount: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="PENDING")
    pay_url: Mapped[str | None] = mapped_column(sa.Text)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    result_code: Mapped[str | None] = mapped_column(sa.String(60))
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_reconciled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    invoice: Mapped[Invoice] = relationship(back_populates="attempts")
    receipts: Mapped[list[PaymentWebhookReceipt]] = relationship(back_populates="attempt")
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        status_check("status_values", "status", "PENDING", "SUCCESS", "FAILED", "EXPIRED"),
        Index("uq_payment_success_invoice", "invoice_id", unique=True, postgresql_where=text("status = 'SUCCESS'")),
        Index("uq_payment_pending_invoice", "invoice_id", unique=True, postgresql_where=text("status = 'PENDING'")),
    )


class PaymentWebhookReceipt(UUIDPK, Base):
    __tablename__ = "payment_webhook_receipts"
    payment_attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_attempts.id"))
    order_id: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    signature_valid: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    processing_result: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    received_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    attempt: Mapped[PaymentAttempt | None] = relationship(back_populates="receipts")
    __table_args__ = (
        status_check("result_values", "processing_result", "PROCESSED", "DUPLICATE", "INVALID_SIGNATURE", "UNKNOWN_ORDER", "AMOUNT_MISMATCH", "RECONCILIATION_REQUIRED"),
        Index("ix_payment_webhook_order", "order_id"),
    )


class InvoiceAccessToken(UUIDPK, Base):
    __tablename__ = "invoice_access_tokens"
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    invoice: Mapped[Invoice] = relationship(back_populates="tokens")


class BillingRun(UUIDPK, Base):
    __tablename__ = "billing_runs"
    billing_month: Mapped[date] = mapped_column(sa.Date, nullable=False)
    trigger_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    issued_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    waiting_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    skipped_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    failed_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    __table_args__ = (
        status_check("trigger_values", "trigger_type", "SCHEDULED", "MANUAL"),
        status_check("status_values", "status", "RUNNING", "COMPLETED", "FAILED"),
        CheckConstraint("issued_count >= 0 AND waiting_count >= 0 AND skipped_count >= 0 AND failed_count >= 0", name="counts_nonnegative"),
        Index("ix_billing_runs_month", "billing_month"),
    )


class OutboxEvent(UUIDPK, Base):
    __tablename__ = "outbox_events"
    aggregate_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    event_version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    dedupe_key: Mapped[str | None] = mapped_column(sa.String(180), unique=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(sa.Text)
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        Index("ix_billing_outbox_unpublished", "created_at", postgresql_where=text("published_at IS NULL")),
    )

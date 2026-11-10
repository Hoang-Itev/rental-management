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

class EmailJob(UUIDPK, AuditTimes, Base):
    __tablename__ = "email_jobs"
    source_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    email_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Billing logical ref
    recipient_email: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    subject: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    template_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="PENDING")
    attempt_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(sa.Text)
    provider_message_id: Mapped[str | None] = mapped_column(sa.String(255))
    __table_args__ = (
        status_check("email_type_values", "email_type", "INVOICE", "REMINDER", "PAYMENT_RECEIPT", "CONTRACT_EXPIRING"),
        status_check("status_values", "status", "PENDING", "SENDING", "SENT", "FAILED", "SKIPPED"),
        CheckConstraint("attempt_count >= 0", name="attempts_nonnegative"),
        Index("ix_email_jobs_due", "status", "next_attempt_at"),
    )

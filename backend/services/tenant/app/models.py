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

class Tenant(UUIDPK, AuditTimes, Base):
    __tablename__ = "tenants"
    full_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(sa.String(30))
    email: Mapped[str | None] = mapped_column(sa.String(254))
    note: Mapped[str | None] = mapped_column(sa.Text)
    contracts: Mapped[list[Contract]] = relationship(back_populates="representative")


class Contract(UUIDPK, AuditTimes, Base):
    __tablename__ = "contracts"
    contract_code: Mapped[str] = mapped_column(sa.String(60), nullable=False, unique=True)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # Room logical ref
    room_code_snapshot: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    representative_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)  # inclusive business end date
    actual_end_date: Mapped[date | None] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="DRAFT")
    deposit_amount: Mapped[int | None] = mapped_column(sa.BigInteger)
    end_reason: Mapped[str | None] = mapped_column(sa.Text)
    representative: Mapped[Tenant] = relationship(back_populates="contracts")
    terms: Mapped[list[ContractTerm]] = relationship(back_populates="contract")
    history: Mapped[list[ContractEvent]] = relationship(back_populates="contract")
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="date_order"),
        CheckConstraint("actual_end_date IS NULL OR (actual_end_date BETWEEN start_date AND end_date)", name="actual_end_valid"),
        CheckConstraint("deposit_amount IS NULL OR deposit_amount >= 0", name="deposit_nonnegative"),
        status_check("status_values", "status", "DRAFT", "SCHEDULED", "ACTIVE", "EXPIRED_PENDING", "ENDED", "CANCELLED"),
        # btree_gist is created in the initial Alembic migration (tenant_db only).
        # EXPIRED_PENDING's post-end physical occupancy is still guarded by
        # the activation transaction, not a fictitious infinite SQL range.
        ExcludeConstraint(
            ("room_id", "="),
            (text("daterange(start_date, end_date + 1, '[)')"), "&&"),
            name="ex_contracts_room_period",
            where=text("status IN ('SCHEDULED','ACTIVE','EXPIRED_PENDING')"),
            using="gist",
        ),
        Index("ix_contracts_room_status", "room_id", "status"),
    )


class ContractTerm(UUIDPK, Base):
    __tablename__ = "contract_terms"
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(sa.Date)  # exclusive, NULL = unbounded
    monthly_rent: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    electricity_unit_price: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    water_unit_price: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    monthly_service_fee: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    contract: Mapped[Contract] = relationship(back_populates="terms")
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="term_date_order"),
        CheckConstraint("monthly_rent >= 0 AND electricity_unit_price >= 0 AND water_unit_price >= 0 AND monthly_service_fee >= 0", name="price_nonnegative"),
        ExcludeConstraint(
            ("contract_id", "="),
            (text("daterange(effective_from, effective_to, '[)')"), "&&"),
            name="ex_contract_terms_period",
            using="gist",
        ),
    )


class ContractEvent(UUIDPK, Base):
    __tablename__ = "contract_events"
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Auth logical ref
    reason: Mapped[str | None] = mapped_column(sa.Text)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    contract: Mapped[Contract] = relationship(back_populates="history")
    __table_args__ = (
        status_check("event_types", "event_type", "CREATED", "CONFIRMED", "STARTED", "EXTENDED", "TERMINATION_RECORDED", "ENDED", "CANCELLED"),
        Index("ix_contract_events_contract_time", "contract_id", "occurred_at"),
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
        Index("ix_tenant_outbox_unpublished", "created_at", postgresql_where=text("published_at IS NULL")),
    )

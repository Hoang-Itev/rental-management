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

class Meter(UUIDPK, AuditTimes, Base):
    __tablename__ = "meters"
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # Room logical ref
    meter_code: Mapped[str] = mapped_column(sa.String(80), nullable=False, unique=True)
    meter_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    unit: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    initial_reading: Mapped[Decimal] = mapped_column(sa.Numeric(16, 3), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="ACTIVE")
    last_received_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    readings: Mapped[list[MeterReading]] = relationship(back_populates="meter")
    cutoffs: Mapped[list[MeterCutoff]] = relationship(back_populates="meter")
    alerts: Mapped[list[MeterAlert]] = relationship(back_populates="meter")
    __table_args__ = (
        sa.UniqueConstraint("room_id", "meter_type", name="uq_meters_room_type"),
        status_check("meter_type_values", "meter_type", "ELECTRICITY", "WATER"),
        CheckConstraint("(meter_type = 'ELECTRICITY' AND unit = 'KWH') OR (meter_type = 'WATER' AND unit = 'M3')", name="unit_matches_type"),
        CheckConstraint("initial_reading >= 0", name="initial_nonnegative"),
        status_check("status_values", "status", "ACTIVE", "INACTIVE"),
    )


class MeterReading(Base):
    __tablename__ = "meter_readings"
    meter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meters.id"), primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)
    reading_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 3), nullable=False)
    received_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    validation_status: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="VALID")
    anomaly_reason: Mapped[str | None] = mapped_column(sa.Text)
    meter: Mapped[Meter] = relationship(back_populates="readings")
    __table_args__ = (
        CheckConstraint("reading_value >= 0", name="reading_nonnegative"),
        status_check("validation_values", "validation_status", "VALID", "SUSPECT", "REJECTED"),
        Index("ix_meter_readings_valid_time", "meter_id", "measured_at", postgresql_where=text("validation_status = 'VALID'")),
    )


class MeterCutoff(UUIDPK, Base):
    __tablename__ = "meter_cutoffs"
    meter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meters.id"), nullable=False)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Tenant logical ref
    cutoff_type: Mapped[str] = mapped_column(sa.String(25), nullable=False)
    cutoff_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    reading_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(16, 3))
    source: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    source_reading_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    manual_reason: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="PENDING")
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Auth logical ref
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("meter_cutoffs.id"))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    meter: Mapped[Meter] = relationship(back_populates="cutoffs")
    __table_args__ = (
        status_check("cutoff_type_values", "cutoff_type", "CONTRACT_START", "CONTRACT_END", "MONTHLY"),
        status_check("source_values", "source", "AUTOMATIC", "MANUAL"),
        status_check("status_values", "status", "PENDING", "CONFIRMED", "SUPERSEDED"),
        CheckConstraint("reading_value IS NULL OR reading_value >= 0", name="reading_nonnegative"),
        CheckConstraint("status <> 'CONFIRMED' OR (reading_value IS NOT NULL AND confirmed_at IS NOT NULL)", name="confirmed_complete"),
        CheckConstraint("source <> 'MANUAL' OR (manual_reason IS NOT NULL AND confirmed_by IS NOT NULL)", name="manual_audit_required"),
        # One effective physical reading per meter/time, shared by all business reasons.
        Index(
            "uq_meter_cutoffs_active_time", "meter_id", "cutoff_at",
            unique=True, postgresql_where=text("status <> 'SUPERSEDED'"),
        ),
    )


class MeterAlert(UUIDPK, Base):
    __tablename__ = "meter_alerts"
    meter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meters.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="OPEN")
    related_measured_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    related_cutoff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("meter_cutoffs.id"))
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(sa.Text)
    meter: Mapped[Meter] = relationship(back_populates="alerts")
    __table_args__ = (
        status_check("alert_type_values", "alert_type", "OFFLINE", "READING_DECREASE", "LATE_AFTER_CUTOFF", "CONFLICTING_DUPLICATE"),
        status_check("status_values", "status", "OPEN", "RESOLVED"),
        Index("uq_meter_alerts_open_offline", "meter_id", unique=True, postgresql_where=text("status = 'OPEN' AND alert_type = 'OFFLINE'")),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())

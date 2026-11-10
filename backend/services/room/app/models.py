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

class Property(UUIDPK, AuditTimes, Base):
    __tablename__ = "properties"
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    address: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="ACTIVE")
    buildings: Mapped[list[Building]] = relationship(back_populates="property")
    __table_args__ = (status_check("status_values", "status", "ACTIVE", "INACTIVE"),)


class Building(UUIDPK, AuditTimes, Base):
    __tablename__ = "buildings"
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="ACTIVE")
    property: Mapped[Property] = relationship(back_populates="buildings")
    floors: Mapped[list[Floor]] = relationship(back_populates="building")
    __table_args__ = (
        sa.UniqueConstraint("property_id", "name", name="uq_buildings_property_name"),
        status_check("status_values", "status", "ACTIVE", "INACTIVE"),
    )


class Floor(UUIDPK, AuditTimes, Base):
    __tablename__ = "floors"
    building_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=False)
    floor_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(sa.String(120))
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="ACTIVE")
    building: Mapped[Building] = relationship(back_populates="floors")
    rooms: Mapped[list[Room]] = relationship(back_populates="floor")
    __table_args__ = (
        sa.UniqueConstraint("building_id", "floor_number", name="uq_floors_building_number"),
        status_check("status_values", "status", "ACTIVE", "INACTIVE"),
    )


class Room(UUIDPK, AuditTimes, Base):
    __tablename__ = "rooms"
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    floor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), nullable=False)
    room_code: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    area_m2: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), nullable=False)
    listed_rent: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="ACTIVE")
    occupancy_contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # Tenant logical ref
    occupancy_updated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    floor: Mapped[Floor] = relationship(back_populates="rooms")
    property: Mapped[Property] = relationship()
    __table_args__ = (
        sa.UniqueConstraint("property_id", "room_code", name="uq_rooms_property_code"),
        CheckConstraint("area_m2 > 0", name="area_positive"),
        CheckConstraint("listed_rent >= 0", name="rent_nonnegative"),
        status_check("status_values", "status", "ACTIVE", "INACTIVE"),
        Index("ix_rooms_occupancy_contract_id", "occupancy_contract_id"),
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
        Index("ix_room_outbox_unpublished", "created_at", postgresql_where=text("published_at IS NULL")),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())

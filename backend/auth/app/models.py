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

class User(UUIDPK, AuditTimes, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (
        # Case-insensitive uniqueness regardless of application-side normalization.
        Index("uq_users_email_ci", func.lower(email), unique=True),
    )

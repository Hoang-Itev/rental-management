"""P07 cutoff domain policy. Vietnam civil month, event instants stored in UTC.

At a boundary pick the closest VALID sample within +/-15 minutes, breaking
an equidistant tie in favour of the sample at/before the boundary. Wait until
15 minutes after the boundary so late-arriving near-boundary samples can arrive.
Confirmed cutoffs are immutable except for their superseded status; explicit
manual correction creates a new, auditable version.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

WINDOW = timedelta(minutes=15)
OFFLINE_AFTER = timedelta(minutes=20)
VN = timezone(timedelta(hours=7))  # Vietnam has no daylight-saving time.


class CutoffError(ValueError):
    def __init__(self, detail: str, status: int = 409):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('timezone-aware datetime required')
    return value.astimezone(timezone.utc)


def month_start(instant: datetime) -> datetime:
    local = utc(instant).astimezone(VN)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def next_month(boundary: datetime) -> datetime:
    local = utc(boundary).astimezone(VN)
    year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    return datetime(year, month, 1, tzinfo=VN).astimezone(timezone.utc)


def previous_month(boundary: datetime) -> datetime:
    local = utc(boundary).astimezone(VN)
    year, month = (local.year - 1, 12) if local.month == 1 else (local.year, local.month - 1)
    return datetime(year, month, 1, tzinfo=VN).astimezone(timezone.utc)


def decimal_3(value: Decimal) -> Decimal:
    v = Decimal(value)
    if not v.is_finite() or v < 0 or v.as_tuple().exponent < -3:
        raise CutoffError('Reading must be non-negative and have at most 3 decimal places', 422)
    if v >= Decimal('10000000000000'):
        raise CutoffError('Reading exceeds the database numeric(16,3) limit', 422)
    return v


def db_utc(value: datetime) -> datetime:
    # SQLAlchemy SQLite unit fixture strips timezone, PostgreSQL does not.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else utc(value)

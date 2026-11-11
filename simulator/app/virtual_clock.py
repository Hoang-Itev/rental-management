
"""Deterministic cumulative meter readings based on a known meter baseline."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from uuid import UUID

from app.config import Settings

THREE = Decimal("0.001")
SECONDS_PER_DAY = Decimal(86400)


def canonical_time(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise ValueError("Measurement must be timezone aware")
    return instant.astimezone(timezone.utc).replace(microsecond=0)


class VirtualClock:
    def __init__(self, settings: Settings):
        self.settings = settings

    def reading(
        self,
        meter_id: UUID,
        meter_type: str,
        instant: datetime,
        *,
        base_reading: Decimal | int | str = 0,
        base_time: datetime | None = None,
    ) -> Decimal:
        instant = canonical_time(instant)

        origin = canonical_time(
            base_time if base_time is not None else self.settings.epoch
        )

        baseline = Decimal(str(base_reading))

        if not baseline.is_finite() or baseline < 0:
            raise ValueError("Invalid baseline reading")

        elapsed = max(
            Decimal(0),
            Decimal(str((instant - origin).total_seconds()))
        )

        variation = Decimal(
            875 + int.from_bytes(
                sha256(meter_id.bytes).digest()[:2], "big"
            ) % 251
        ) / Decimal(1000)

        if meter_type == "ELECTRICITY":
            per_day = self.settings.electricity_kwh_per_day
        elif meter_type == "WATER":
            per_day = self.settings.water_m3_per_day
        else:
            raise ValueError("Unsupported meter type")

        consumption = (
            elapsed
            * self.settings.time_scale
            * per_day
            * variation
            / SECONDS_PER_DAY
        )

        return (baseline + consumption).quantize(
            THREE,
            rounding=ROUND_HALF_UP
        )

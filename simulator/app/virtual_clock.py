"""Deterministic cumulative consumption. Event time always uses real UTC.

Fixed origin + fixed rates guarantee monotone values across simulator restarts,
independent of polling/reconnection. SIM_TIME_SCALE accelerates consumption only.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from uuid import UUID
from app.config import Settings

THREE = Decimal('0.001')
SECONDS_PER_DAY = Decimal(86400)

def canonical_time(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise ValueError('Measurement must be timezone aware')
    return instant.astimezone(timezone.utc).replace(microsecond=0)

class VirtualClock:
    def __init__(self, settings: Settings):
        self.settings = settings

    def reading(self, meter_id: UUID, meter_type: str, instant: datetime) -> Decimal:
        instant = canonical_time(instant)
        epoch = self.settings.epoch.astimezone(timezone.utc)
        delta = max(Decimal(0), Decimal(str((instant - epoch).total_seconds())))
        # +- 12.5% deterministic per meter. No random resets on process restart.
        variation = Decimal(875 + int.from_bytes(sha256(meter_id.bytes).digest()[:2], 'big') % 251) / Decimal(1000)
        if meter_type == 'ELECTRICITY':
            per_day = self.settings.electricity_kwh_per_day
        elif meter_type == 'WATER':
            per_day = self.settings.water_m3_per_day
        else:
            raise ValueError('Unsupported meter type')
        return (delta * self.settings.time_scale * per_day * variation / SECONDS_PER_DAY).quantize(
            THREE, rounding=ROUND_HALF_UP
        )

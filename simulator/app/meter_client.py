"""Internal service-token HTTP meter listing with pagination and validation."""
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
import httpx
from app.config import Settings
from datetime import datetime
from decimal import Decimal

@dataclass(frozen=True)
class Meter:
    id: UUID
    room_id: UUID
    meter_type: str

    @classmethod
    def parse(cls, row: dict) -> 'Meter':
        if row.get('meter_type') not in ('ELECTRICITY','WATER') or row.get('status') != 'ACTIVE':
            raise ValueError('Invalid/non-active meter from Metering')
        return cls(id=UUID(row['id']), room_id=UUID(row['room_id']), meter_type=row['meter_type'])


@dataclass(frozen=True)
class MeterBaseline:
    reading_value: Decimal
    measured_at: datetime


class MeterClient:
    def __init__(self, settings: Settings, *, transport=None):
        self.settings = settings
        self.transport = transport

    def list_active(self) -> list[Meter]:
        page, total, collected = 1, None, []
        ids = set()
        with httpx.Client(base_url=self.settings.metering_url.rstrip('/'), timeout=8,
                          transport=self.transport, trust_env=False) as client:
            while True:
                response = client.get('/internal/v1/meters',
                    params={'status':'ACTIVE','page':page,'page_size':100},
                    headers={'X-Service-Token':self.settings.service_token})
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get('items'), list):
                    raise ValueError('Meter listing response is malformed')
                meta = body.get('meta',{})
                current_total = meta.get('total')
                if not isinstance(current_total, int) or current_total < 0:
                    raise ValueError('Invalid listing total')
                if total is None:
                    total = current_total
                items = body['items']
                if not items and len(collected) < total:
                    raise ValueError('Meter listing ended before total')
                for entry in items:
                    meter = Meter.parse(entry)
                    if meter.id in ids:
                        raise ValueError('Duplicate meter ID across pages')
                    ids.add(meter.id)
                    collected.append(meter)
                if len(collected) >= total:
                    if len(collected) != total:
                        raise ValueError('Meter listing exceeded stated total')
                    return collected
                page += 1
                if page > 10000:
                    raise ValueError('Meter listing pagination exceeded safety cap')

    def get_baseline(self, meter_id: UUID) -> MeterBaseline:
        with httpx.Client(
            base_url=self.settings.metering_url.rstrip("/"),
            timeout=8,
            transport=self.transport,
            trust_env=False,
        ) as client:
            response = client.get(
                f"/internal/v1/meters/{meter_id}/baseline",
                headers={
                    "X-Service-Token": self.settings.service_token
                },
            )
            response.raise_for_status()
            body = response.json()

        value = Decimal(str(body["reading_value"]))
        measured_at = datetime.fromisoformat(
            body["measured_at"].replace("Z", "+00:00")
        )

        if not value.is_finite() or value < 0:
            raise ValueError("Invalid baseline value")

        if measured_at.tzinfo is None:
            raise ValueError("Baseline timestamp must include timezone")

        return MeterBaseline(
            reading_value=value,
            measured_at=measured_at,
        )

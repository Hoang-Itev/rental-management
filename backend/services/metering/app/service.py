"""Handle RoomCreated exactly once as a business effect (at-least-once delivery)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.orm import Session

from app import repository as repo


class RoomCreatedData(BaseModel):
    room_id: UUID
    property_id: UUID
    floor_id: UUID
    room_code: str


class RoomCreatedEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_id: UUID
    event_type: Literal["RoomCreated"]
    event_version: Literal[1]
    occurred_at: datetime
    correlation_id: UUID
    aggregate_id: UUID
    data: RoomCreatedData

    @model_validator(mode="after")
    def matching_aggregate(self):
        if self.aggregate_id != self.data.room_id:
            raise ValueError("RoomCreated aggregate_id must equal data.room_id")
        return self


class MeteringService:
    def __init__(self, session: Session):
        self.session = session

    @contextmanager
    def atomic(self):
        tx = self.session.begin_nested() if self.session.in_transaction() else self.session.begin()
        with tx:
            yield

    def process_room_created(self, raw: dict) -> bool:
        """True if this event ID was new. Creates exactly ELECTRICITY and WATER.

        Atomic: processed_events row and both meters commit (or roll back) together.
        PostgreSQL unique constraints protect against concurrent duplicate events,
        including distinct event IDs for the same room.
        """
        event = RoomCreatedEnvelope.model_validate(raw)
        with self.atomic():
            inserted = repo.mark_processed(self.session, event.event_id, event.event_type)
            if inserted:
                repo.ensure_meter(self.session, event.data.room_id, "ELECTRICITY")
                repo.ensure_meter(self.session, event.data.room_id, "WATER")
        return inserted

    def meters_for_room(self, room_id: UUID):
        return repo.meters_for_room(self.session, room_id)

    def list_meters(self, status: str | None = "ACTIVE", page: int = 1, page_size: int = 100):
        return repo.list_meters(self.session, status=status, page=page, page_size=page_size)


    def process_contract_event(self, raw: dict, *, now: datetime | None = None) -> bool:
        from app.lifecycle import ContractEnvelope, FutureEvent
        event=ContractEnvelope.model_validate(raw)
        now=now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if event.effective_at > now:
            raise FutureEvent('Contract boundary is not due')
        with self.atomic():
            inserted=repo.mark_processed(self.session,event.event_id,event.event_type)
            if inserted:
                repo.ensure_handover_cutoffs(self.session,event.data.room_id,
                    event.data.contract_id,event.effective_at, event.event_type)
        return inserted

    def record_telemetry(self, raw: dict, *, routing_key: str | None = None,
                         now: datetime | None = None) -> str:
        """Return inserted, duplicate, conflict or suspect; commit effect atomically.

        Duplicates are keyed on (meter_id, measured_at). A different value for
        the same key does not overwrite evidence; it creates one alert per key.
        Out-of-order samples are compared to temporal neighbours (not arrival
        order), so valid late arrivals are still stored as VALID.
        """
        from datetime import timedelta
        from decimal import Decimal
        from uuid import uuid4
        from app import models as m, schemas as s
        from app.telemetry import InvalidTelemetry, UnknownMeter
        from sqlalchemy.orm import Session

        sample = s.Telemetry.model_validate(raw)
        if routing_key is not None and routing_key != f'meters.{sample.meter_id}.reading':
            raise InvalidTelemetry('MQTT topic meter_id does not match payload')
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if sample.measured_at > now.astimezone(timezone.utc) + timedelta(minutes=5):
            raise InvalidTelemetry('Reading is too far into the future')

        with self.atomic():
            meter = repo.meter_locked(self.session, sample.meter_id)
            if meter is None or meter.status != 'ACTIVE':
                raise UnknownMeter('Meter is unknown or INACTIVE')
            previous = repo.reading_at(self.session, sample.meter_id, sample.measured_at)
            if previous is not None:
                if previous.reading_value == sample.reading_value:
                    return 'duplicate'
                if not repo.existing_alert(self.session, sample.meter_id,
                                           sample.measured_at, 'CONFLICTING_DUPLICATE'):
                    self.session.add(m.MeterAlert(
                        id=uuid4(), meter_id=sample.meter_id,
                        alert_type='CONFLICTING_DUPLICATE', status='OPEN',
                        related_measured_at=sample.measured_at,
                        detail={'stored': str(previous.reading_value),
                                'incoming': str(sample.reading_value)},
                    ))
                    self.session.flush()
                return 'conflict'

            older = repo.nearest_valid(self.session, sample.meter_id,
                                       sample.measured_at, before=True)
            newer = repo.nearest_valid(self.session, sample.meter_id,
                                       sample.measured_at, before=False)
            lower_breach = older is not None and sample.reading_value < older.reading_value
            upper_breach = newer is not None and sample.reading_value > newer.reading_value
            suspect = lower_breach or upper_breach
            reason = ('READING_DECREASE' if lower_breach else
                      'OUT_OF_ORDER_NON_MONOTONIC' if upper_breach else None)
            self.session.add(m.MeterReading(
                meter_id=sample.meter_id, measured_at=sample.measured_at,
                reading_value=sample.reading_value,
                validation_status='SUSPECT' if suspect else 'VALID',
                anomaly_reason=reason,
            ))
            if suspect:
                self.session.add(m.MeterAlert(
                    id=uuid4(), meter_id=sample.meter_id,
                    alert_type='READING_DECREASE', status='OPEN',
                    related_measured_at=sample.measured_at,
                    detail={'incoming': str(sample.reading_value),
                            'before': str(older.reading_value) if older is not None else None,
                            'after': str(newer.reading_value) if newer is not None else None},
                ))
            meter.last_received_at = now
            self.session.flush()
        return 'suspect' if suspect else 'inserted'

    def readings_for_meter(self, meter_id: UUID, *, page=1, page_size=100, from_at=None, to_at=None):
        from app.telemetry import UnknownMeter
        from app import models as m
        if self.session.get(m.Meter, meter_id) is None:
            raise UnknownMeter('Meter not found')
        return repo.readings_for_meter(self.session, meter_id, page=page, page_size=page_size, from_at=from_at, to_at=to_at)

    def alerts_for_meter(self, meter_id: UUID, *, page=1, page_size=100):
        from app.telemetry import UnknownMeter
        from app import models as m
        if self.session.get(m.Meter, meter_id) is None:
            raise UnknownMeter('Meter not found')
        return repo.alerts_for_meter(self.session, meter_id, page=page, page_size=page_size)

    def list_alerts(self, *, status=None, alert_type=None, page=1, page_size=100):
        return repo.list_alerts(self.session, status=status, alert_type=alert_type,
                                page=page, page_size=page_size)

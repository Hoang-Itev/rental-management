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
                meter.last_received_at = now
                repo.resolve_offline(self.session, sample.meter_id, now)
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
            # A late, *better* VALID sample raises an alert for manual review.
            # Never mutate a CONFIRMED cutoff automatically after invoicing.
            if not suspect:
                from app.cutoffs import WINDOW, db_utc
                for cutoff in repo.current_confirmed_near_reading(
                    self.session, sample.meter_id, sample.measured_at, WINDOW
                ):
                    if (cutoff.source_reading_at is not None and
                        db_utc(cutoff.confirmed_at) < now and
                        abs(sample.measured_at - db_utc(cutoff.cutoff_at)) <
                        abs(db_utc(cutoff.source_reading_at) - db_utc(cutoff.cutoff_at)) and
                        repo.alert_for_cutoff(self.session, cutoff.id,
                                              sample.meter_id, 'LATE_AFTER_CUTOFF') is None):
                        self.session.add(m.MeterAlert(
                            id=uuid4(), meter_id=sample.meter_id,
                            alert_type='LATE_AFTER_CUTOFF', status='OPEN',
                            related_measured_at=sample.measured_at,
                            related_cutoff_id=cutoff.id,
                            detail={'cutoff_id': str(cutoff.id),
                                    'confirmed_value': str(cutoff.reading_value),
                                    'late_value': str(sample.reading_value)},
                        ))
            meter.last_received_at = now
            repo.resolve_offline(self.session, sample.meter_id, now)
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

    def meter_baseline(self, meter_id: UUID):
        from app import models as m
        from app.telemetry import UnknownMeter
        meter = self.session.get(m.Meter, meter_id)
        if meter is None or meter.status != 'ACTIVE':
            raise UnknownMeter('Meter not found or inactive')
        latest = repo.latest_valid_reading(self.session, meter_id)
        if latest is not None:
            return {'reading_value': latest.reading_value, 'measured_at': latest.measured_at,
                    'source': 'LATEST_VALID'}
        return {'reading_value': meter.initial_reading, 'measured_at': meter.created_at,
                'source': 'INITIAL'}

    # P07 cutoff lifecycle. All mutating operations lock the physical meter row,
    # which serializes scheduler, owner corrections and telemetry on PostgreSQL.
    def _cutoff(self, cutoff_id: UUID):
        from app import models as m
        from app.cutoffs import CutoffError
        cutoff = self.session.get(m.MeterCutoff, cutoff_id)
        if cutoff is None:
            raise CutoffError('Cutoff not found', 404)
        return cutoff

    def cutoff(self, cutoff_id: UUID):
        return self._cutoff(cutoff_id)

    def cutoff_reasons(self, cutoff_id: UUID):
        return repo.cutoff_reasons(self.session, cutoff_id)

    def list_cutoffs(self, **filters):
        return repo.list_cutoffs(self.session, **filters)

    def _monotone_manual(self, cutoff, value):
        """Reject manual values that contradict adjacent CONFIRMED boundaries."""
        from sqlalchemy import select
        from app import models as m
        from app.cutoffs import CutoffError
        prior = self.session.scalar(select(m.MeterCutoff).where(
            m.MeterCutoff.meter_id == cutoff.meter_id,
            m.MeterCutoff.id != cutoff.id,
            m.MeterCutoff.status == 'CONFIRMED',
            m.MeterCutoff.cutoff_at < cutoff.cutoff_at,
        ).order_by(m.MeterCutoff.cutoff_at.desc()).limit(1))
        later = self.session.scalar(select(m.MeterCutoff).where(
            m.MeterCutoff.meter_id == cutoff.meter_id,
            m.MeterCutoff.id != cutoff.id,
            m.MeterCutoff.status == 'CONFIRMED',
            m.MeterCutoff.cutoff_at > cutoff.cutoff_at,
        ).order_by(m.MeterCutoff.cutoff_at.asc()).limit(1))
        if prior is not None and value < prior.reading_value:
            raise CutoffError('Manual reading is below previous confirmed cutoff', 409)
        if later is not None and value > later.reading_value:
            raise CutoffError('Manual reading exceeds next confirmed cutoff', 409)

    def confirm_cutoff(self, cutoff_id: UUID, *, reading_value, reason: str,
                       actor_id: UUID, now: datetime | None = None):
        """Only PENDING can be manually confirmed; confirmed records never overwrite."""
        from app.cutoffs import CutoffError, decimal_3, db_utc, utc
        now = utc(now or datetime.now(timezone.utc))
        value = decimal_3(reading_value)
        if len(reason.strip()) < 8:
            raise CutoffError('A manual reason of at least 8 characters is required', 422)
        with self.atomic():
            cutoff = self._cutoff(cutoff_id)
            repo.meter_locked(self.session, cutoff.meter_id)
            self.session.refresh(cutoff, with_for_update=True)
            if cutoff.status != 'PENDING':
                raise CutoffError('Only PENDING cutoffs can be confirmed', 409)
            if db_utc(cutoff.cutoff_at) > now:
                raise CutoffError('Future cutoff cannot be confirmed', 409)
            self._monotone_manual(cutoff, value)
            cutoff.reading_value = value
            cutoff.source = 'MANUAL'
            cutoff.source_reading_at = None
            cutoff.manual_reason = reason.strip()
            cutoff.confirmed_by = actor_id
            cutoff.confirmed_at = now
            cutoff.status = 'CONFIRMED'
            self.session.flush()
        return cutoff

    def revise_cutoff(self, cutoff_id: UUID, *, reading_value, reason: str,
                      actor_id: UUID, now: datetime | None = None):
        """Explicit version: SUPERSEDED old row + fresh CONFIRMED manual row.

        MeterCutoffReason rows remain on the historic version and are copied to
        the current version so handovers remain queryable by contract.
        """
        from uuid import uuid4
        from app import models as m
        from app.cutoffs import CutoffError, decimal_3, db_utc, utc
        now = utc(now or datetime.now(timezone.utc))
        value = decimal_3(reading_value)
        if len(reason.strip()) < 8:
            raise CutoffError('A correction reason of at least 8 characters is required', 422)
        with self.atomic():
            old = self._cutoff(cutoff_id)
            repo.meter_locked(self.session, old.meter_id)
            self.session.refresh(old, with_for_update=True)
            if old.status != 'CONFIRMED':
                raise CutoffError('Only a current CONFIRMED cutoff can be revised', 409)
            if old.reading_value == value:
                raise CutoffError('New reading must differ from previous version', 409)
            self._monotone_manual(old, value)
            reasons = repo.cutoff_reasons(self.session, old.id)
            old.status = 'SUPERSEDED'
            self.session.flush()  # release partial unique key before creating replacement
            replacement = m.MeterCutoff(
                id=uuid4(), meter_id=old.meter_id, contract_id=old.contract_id,
                cutoff_type=old.cutoff_type, cutoff_at=old.cutoff_at,
                reading_value=value, source='MANUAL', source_reading_at=None,
                manual_reason=reason.strip(), status='CONFIRMED', confirmed_at=now,
                confirmed_by=actor_id, supersedes_id=old.id,
            )
            self.session.add(replacement)
            self.session.flush()
            for item in reasons:
                self.session.add(m.MeterCutoffReason(
                    id=uuid4(), cutoff_id=replacement.id,
                    contract_id=item.contract_id, reason_type=item.reason_type,
                ))
            self.session.flush()
        return replacement

    def create_monthly_cutoffs(self, *, now: datetime | None = None, months_back: int = 24,
                               target_boundary: datetime | None = None):
        """Backfill at most 24 months, from meter creation, no duplicate active scope.

        Period end-exclusive: a cutoff at 00:00 VN on the first of month N
        closes month N-1. The meter itself need not have an active contract.
        """
        from uuid import uuid4
        from app import models as m
        from app.cutoffs import WINDOW, CutoffError, month_start, next_month, previous_month, db_utc, utc
        now = utc(now or datetime.now(timezone.utc))
        if not 1 <= months_back <= 120:
            raise CutoffError('months_back must be between 1 and 120', 422)
        boundary = month_start(now)
        if target_boundary is not None:
            target_boundary = utc(target_boundary)
            if target_boundary != month_start(target_boundary):
                raise CutoffError('cutoff_at must be the first of month at 00:00 Vietnam time', 422)
            if target_boundary + WINDOW > now:
                raise CutoffError('Monthly cutoff window has not ended', 409)
            boundary = target_boundary
        earliest = boundary
        if target_boundary is None:
            for _ in range(months_back - 1):
                earliest = previous_month(earliest)
        meters, _ = repo.list_meters(self.session, status='ACTIVE', page=1, page_size=100)
        # pagination avoids silently ignoring projects with over 100 meters
        all_meters = list(meters)
        page = 2
        while len(meters) == 100:
            meters, _ = repo.list_meters(self.session, status='ACTIVE', page=page, page_size=100)
            all_meters.extend(meters)
            page += 1
        count = 0
        for item in all_meters:
            meter = repo.meter_locked(self.session, item.id)
            if meter.status != 'ACTIVE':
                continue
            occupied = repo.active_cutoff_times(self.session, meter.id, earliest, boundary)
            current = earliest
            while current <= boundary:
                if current >= db_utc(meter.created_at) and current + WINDOW <= now:
                    if current not in occupied:
                        self.session.add(m.MeterCutoff(
                            id=uuid4(), meter_id=meter.id, contract_id=None,
                            cutoff_type='MONTHLY', cutoff_at=current,
                            source='AUTOMATIC', status='PENDING',
                        ))
                        self.session.flush()
                        occupied.add(current)
                        count += 1
                current = next_month(current)
        return count

    def finalize_due_cutoffs(self, *, now: datetime | None = None,
                             only_at: datetime | None = None):
        """Wait for +/-15m window; closest VALID within tolerance or leave PENDING."""
        from app.cutoffs import WINDOW, db_utc, utc
        now = utc(now or datetime.now(timezone.utc))
        confirmed = 0
        pending_ids = repo.pending_cutoff_ids(self.session, now - WINDOW)
        only_at = utc(only_at) if only_at is not None else None
        for cutoff_id in pending_ids:
            cutoff = self._cutoff(cutoff_id)
            if only_at is not None and db_utc(cutoff.cutoff_at) != only_at:
                continue
            repo.meter_locked(self.session, cutoff.meter_id)
            self.session.refresh(cutoff, with_for_update=True)
            if cutoff.status != 'PENDING' or db_utc(cutoff.cutoff_at) + WINDOW > now:
                continue
            candidate = repo.closest_valid(self.session, cutoff.meter_id,
                                          db_utc(cutoff.cutoff_at), WINDOW)
            if candidate is None:
                continue
            cutoff.reading_value = candidate.reading_value
            cutoff.source_reading_at = candidate.measured_at
            cutoff.source = 'AUTOMATIC'
            cutoff.status = 'CONFIRMED'
            cutoff.confirmed_at = now
            confirmed += 1
        self.session.flush()
        return confirmed

    def scan_offline(self, *, now: datetime | None = None, offline_minutes: int = 20):
        """An OPEN OFFLINE alert is unique per meter; a new reading resolves it."""
        from uuid import uuid4
        from datetime import timedelta
        from app import models as m
        from app.cutoffs import CutoffError, db_utc, utc
        now = utc(now or datetime.now(timezone.utc))
        if not 1 <= offline_minutes <= 1440:
            raise CutoffError('offline_minutes must be 1..1440', 422)
        meters, total = repo.list_meters(self.session, status='ACTIVE', page=1, page_size=100)
        pages = (total + 99) // 100
        created = 0
        # Unsorted iteration does not change correctness; meter row locks serialize.
        for page in range(1, pages + 1):
            if page > 1:
                meters, _ = repo.list_meters(self.session, status='ACTIVE', page=page, page_size=100)
            for meter in meters:
                locked = repo.meter_locked(self.session, meter.id)
                if locked.status != 'ACTIVE':
                    continue
                last = locked.last_received_at or locked.created_at
                if db_utc(last) + timedelta(minutes=offline_minutes) > now:
                    continue
                if repo.open_offline(self.session, meter.id) is None:
                    self.session.add(m.MeterAlert(
                        id=uuid4(), meter_id=meter.id,
                        alert_type='OFFLINE', status='OPEN',
                        detail={'last_seen_at': db_utc(last).isoformat(),
                                'offline_minutes': offline_minutes},
                        detected_at=now,
                    ))
                    self.session.flush()
                    created += 1
        return created

    def run_cutoff_jobs(self, *, now: datetime | None = None,
                        offline_minutes: int = 20, months_back: int = 24):
        now = now or datetime.now(timezone.utc)
        with self.atomic():
            new_monthly = self.create_monthly_cutoffs(now=now, months_back=months_back)
            confirmed = self.finalize_due_cutoffs(now=now)
            offline = self.scan_offline(now=now, offline_minutes=offline_minutes)
        return {'monthly_created': new_monthly, 'auto_confirmed': confirmed,
                'offline_alerts_created': offline}


    def resolve_meter_alert(self, alert_id: UUID, *, note: str, now: datetime | None = None):
        from app import models as m
        from app.cutoffs import CutoffError, utc
        now = utc(now or datetime.now(timezone.utc))
        if len(note.strip()) < 8:
            raise CutoffError('Resolution note must have at least 8 characters', 422)
        with self.atomic():
            alert = self.session.get(m.MeterAlert, alert_id)
            if alert is None:
                raise CutoffError('Alert not found', 404)
            repo.meter_locked(self.session, alert.meter_id)
            self.session.refresh(alert, with_for_update=True)
            if alert.status != 'OPEN':
                raise CutoffError('Alert is already resolved', 409)
            alert.status = 'RESOLVED'
            alert.resolved_at = now
            alert.resolution_note = note.strip()
            self.session.flush()
        return alert

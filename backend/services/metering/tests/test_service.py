"""Metering RoomCreated dedupe, deterministic meter types, rollback, validation."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app import models as m
from app import repository as repo
from app.service import MeteringService


from tests.support import example


def test_one_room_creates_two_meters(make_session):
    with make_session() as db:
        event = example()
        assert MeteringService(db).process_room_created(event) is True
        meters = MeteringService(db).meters_for_room(UUID(event["data"]["room_id"]))
        assert len(meters) == 2
        assert {(a.meter_type, a.unit) for a in meters} == {
            ("ELECTRICITY", "KWH"), ("WATER", "M3")}
        assert all(a.status == "ACTIVE" for a in meters)


def test_duplicate_event_no_more_meters(make_session):
    with make_session() as db:
        event = example()
        service = MeteringService(db)
        assert service.process_room_created(event) is True
        assert service.process_room_created(event) is False
        assert db.scalar(select(func.count()).select_from(m.Meter)) == 2
        assert db.scalar(select(func.count()).select_from(m.ProcessedEvent)) == 1


def test_different_event_same_room_still_two_meters(make_session):
    with make_session() as db:
        room = uuid4()
        svc = MeteringService(db)
        assert svc.process_room_created(example(room)) is True
        assert svc.process_room_created(example(room)) is True
        assert db.scalar(select(func.count()).select_from(m.Meter)) == 2
        assert db.scalar(select(func.count()).select_from(m.ProcessedEvent)) == 2


def test_database_failure_rolls_back_processed_marker(make_session, monkeypatch):
    with make_session() as db:
        event = example()
        original = repo.ensure_meter
        def fail_water(session, room_id, meter_type):
            if meter_type == "WATER":
                raise RuntimeError("simulated second meter failure")
            return original(session, room_id, meter_type)
        monkeypatch.setattr(repo, "ensure_meter", fail_water)
        with pytest.raises(RuntimeError, match="simulated"):
            MeteringService(db).process_room_created(event)
        assert db.scalar(select(func.count()).select_from(m.Meter)) == 0
        assert db.scalar(select(func.count()).select_from(m.ProcessedEvent)) == 0


@pytest.mark.parametrize("wrong", [
    {"event_type": "Wrong"},
    {"event_version": 2},
    {"aggregate_id": str(uuid4())},
    {"data": {"room_id": "not-a-uuid"}},
])
def test_invalid_events_do_not_write(make_session, wrong):
    with make_session() as db:
        event = example()
        if "data" in wrong:
            event["data"].update(wrong["data"])
        else:
            event.update(wrong)
        with pytest.raises(ValidationError):
            MeteringService(db).process_room_created(event)
        assert db.scalar(select(func.count()).select_from(m.Meter)) == 0


def test_replayed_room_get_same_ids(make_session):
    with make_session() as db:
        event = example()
        svc = MeteringService(db)
        svc.process_room_created(event)
        ids1 = [r.id for r in svc.meters_for_room(UUID(event["data"]["room_id"]))]
        svc.process_room_created(event)
        ids2 = [r.id for r in svc.meters_for_room(UUID(event["data"]["room_id"]))]
        assert len(ids1) == 2 and ids1 == ids2

# P06 MQTT cumulative telemetry regressions.
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.telemetry import InvalidTelemetry, UnknownMeter


def sample(meter_id, stamp='2026-11-11T10:00:00Z', val='100.000'):
    return {'meter_id': str(meter_id), 'measured_at': stamp, 'reading_value': val}


def new_meter(db):
    rid = uuid4()
    repo.ensure_meter(db, rid, 'ELECTRICITY')
    db.flush()
    return MeteringService(db).meters_for_room(rid)[0]


def test_p06_insert_duplicate_conflict_alert_once(make_session):
    with make_session() as db:
        meter = new_meter(db)
        svc = MeteringService(db)
        msg = sample(meter.id)
        assert svc.record_telemetry(msg, routing_key=f'meters.{meter.id}.reading') == 'inserted'
        assert svc.record_telemetry(msg) == 'duplicate'
        changed = {**msg, 'reading_value':'101.000'}
        assert svc.record_telemetry(changed) == 'conflict'
        assert svc.record_telemetry(changed) == 'conflict'
        rows, total = svc.readings_for_meter(meter.id)
        assert total == 1 and rows[0].reading_value == Decimal('100.000')
        alerts, total = svc.alerts_for_meter(meter.id)
        assert total == 1 and alerts[0].alert_type == 'CONFLICTING_DUPLICATE'
        assert alerts[0].detail['stored'] == '100.000'


def test_p06_out_of_order_valid_then_suspect_by_neighbours(make_session):
    with make_session() as db:
        meter = new_meter(db)
        svc = MeteringService(db)
        assert svc.record_telemetry(sample(meter.id, '2026-11-11T12:00:00Z', '120')) == 'inserted'
        assert svc.record_telemetry(sample(meter.id, '2026-11-11T10:00:00Z', '100')) == 'inserted'
        assert svc.record_telemetry(sample(meter.id, '2026-11-11T11:00:00Z', '110')) == 'inserted'
        assert svc.record_telemetry(sample(meter.id, '2026-11-11T09:00:00Z', '130')) == 'suspect'
        assert svc.record_telemetry(sample(meter.id, '2026-11-11T13:00:00Z', '115')) == 'suspect'
        rows, count = svc.readings_for_meter(meter.id)
        assert count == 5
        valid = [r for r in rows if r.validation_status == 'VALID']
        suspect = [r for r in rows if r.validation_status == 'SUSPECT']
        assert len(valid) == 3 and len(suspect) == 2
        assert svc.alerts_for_meter(meter.id)[1] == 2


def test_p06_routing_validation_unknown_future_and_precision(make_session):
    with make_session() as db:
        meter = new_meter(db)
        svc = MeteringService(db)
        with pytest.raises(InvalidTelemetry):
            svc.record_telemetry(sample(meter.id), routing_key=f'meters.{uuid4()}.reading')
        with pytest.raises(UnknownMeter):
            svc.record_telemetry(sample(uuid4()))
        with pytest.raises(InvalidTelemetry):
            svc.record_telemetry(sample(meter.id, '2026-11-11T10:10:00Z'),
                                 now=datetime(2026,11,11,10,tzinfo=timezone.utc))
        with pytest.raises(ValueError):
            svc.record_telemetry(sample(meter.id, val='1.9999'))
        with pytest.raises(ValueError):
            svc.record_telemetry(sample(meter.id, val='-1'))
        db.get(m.Meter, meter.id).status = 'INACTIVE'
        db.flush()
        with pytest.raises(UnknownMeter):
            svc.record_telemetry(sample(meter.id))
        assert svc.readings_for_meter(meter.id)[1] == 0


def test_p06_incoming_duplicate_of_suspect_is_still_idempotent(make_session):
    with make_session() as db:
        meter = new_meter(db)
        svc = MeteringService(db)
        svc.record_telemetry(sample(meter.id, val='200'))
        earlier = sample(meter.id, '2026-11-11T09:00:00Z', '220')
        assert svc.record_telemetry(earlier) == 'suspect'
        assert svc.record_telemetry(earlier) == 'duplicate'
        assert svc.readings_for_meter(meter.id)[1] == 2
        assert svc.alerts_for_meter(meter.id)[1] == 1

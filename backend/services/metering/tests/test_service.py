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

# P07 monthly/contract cutoff selection, manual versioning and offline alarms.
from app.cutoffs import CutoffError, WINDOW, month_start


def _dt(day, hour=0, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


def _insert_reading(db, meter_id, stamp, value, status='VALID'):
    db.add(m.MeterReading(meter_id=meter_id, measured_at=stamp,
                          reading_value=Decimal(str(value)), validation_status=status))
    db.flush()


def _pending(db, meter_id, at, kind='MONTHLY', contract_id=None):
    row = m.MeterCutoff(id=uuid4(), meter_id=meter_id,
        contract_id=contract_id, cutoff_type=kind, cutoff_at=at,
        source='AUTOMATIC', status='PENDING')
    db.add(row)
    db.flush()
    return row


def test_p07_select_valid_nearest_and_reject_outside_15_minutes(make_session):
    with make_session() as db:
        meter = new_meter(db)
        instant = _dt(11, 12)
        row = _pending(db, meter.id, instant)
        _insert_reading(db, meter.id, instant - timedelta(minutes=16), '500')
        _insert_reading(db, meter.id, instant - timedelta(minutes=10), '501', 'SUSPECT')
        svc = MeteringService(db)
        assert svc.finalize_due_cutoffs(now=instant + timedelta(minutes=15)) == 0
        assert row.status == 'PENDING' and row.reading_value is None
        _insert_reading(db, meter.id, instant + timedelta(minutes=15), '503')
        _insert_reading(db, meter.id, instant - timedelta(minutes=15), '502')
        assert svc.finalize_due_cutoffs(now=instant + timedelta(minutes=15)) == 1
        assert row.status == 'CONFIRMED'
        assert row.reading_value == Decimal('502')  # tie -> earlier reading
        assert row.source_reading_at.replace(tzinfo=timezone.utc) == instant - timedelta(minutes=15)
        _insert_reading(db, meter.id, instant, '502.5')
        assert svc.finalize_due_cutoffs(now=instant + timedelta(days=1)) == 0
        assert row.reading_value == Decimal('502')  # immutable


def test_p07_nearest_later_reading_requires_window_elapsed(make_session):
    with make_session() as db:
        meter = new_meter(db)
        instant = _dt(11, 12)
        row = _pending(db, meter.id, instant)
        _insert_reading(db, meter.id, instant + timedelta(minutes=5), '101')
        svc = MeteringService(db)
        assert svc.finalize_due_cutoffs(now=instant + timedelta(minutes=14, seconds=59)) == 0
        assert row.status == 'PENDING'
        assert svc.finalize_due_cutoffs(now=instant + timedelta(minutes=15)) == 1
        assert row.reading_value == Decimal('101')


def test_p07_manual_confirm_requires_actor_reason_and_version(make_session):
    with make_session() as db:
        meter = new_meter(db)
        instant = _dt(11, 12)
        row = _pending(db, meter.id, instant)
        svc = MeteringService(db)
        actor = uuid4()
        with pytest.raises(CutoffError):
            svc.confirm_cutoff(row.id, reading_value='100', reason='short', actor_id=actor,
                               now=_dt(12))
        confirmed = svc.confirm_cutoff(row.id, reading_value='100', reason='Manual meter reading',
                                       actor_id=actor, now=_dt(12))
        assert confirmed.reading_value == 100
        assert confirmed.confirmed_by == actor and confirmed.source == 'MANUAL'
        with pytest.raises(CutoffError) as err:
            svc.confirm_cutoff(row.id, reading_value='101', reason='Manual meter reading',
                               actor_id=actor, now=_dt(12))
        assert err.value.status == 409
        newer = svc.revise_cutoff(row.id, reading_value='102', reason='Corrected on inspection',
                                 actor_id=actor, now=_dt(12))
        assert row.status == 'SUPERSEDED'
        assert newer.supersedes_id == row.id and newer.status == 'CONFIRMED'
        assert newer.reading_value == 102
        assert svc.revise_cutoff(newer.id, reading_value='103', reason='Another correction',
                                actor_id=actor, now=_dt(12)).supersedes_id == newer.id
        with pytest.raises(CutoffError):
            svc.revise_cutoff(row.id, reading_value='104', reason='Stale revision is blocked',
                              actor_id=actor, now=_dt(12))
        assert db.scalar(select(func.count()).select_from(m.MeterCutoff).where(
            m.MeterCutoff.status == 'CONFIRMED')) == 1


def test_p07_manual_monotone_between_confirmed_boundaries(make_session):
    with make_session() as db:
        meter = new_meter(db)
        before = _pending(db, meter.id, _dt(9))
        middle = _pending(db, meter.id, _dt(10))
        after = _pending(db, meter.id, _dt(11))
        svc = MeteringService(db)
        actor = uuid4()
        for row, reading in ((before, '100'), (after, '200')):
            svc.confirm_cutoff(row.id, reading_value=reading,
                               reason='Observed on meter', actor_id=actor, now=_dt(12))
        for reading in ('99', '201'):
            with pytest.raises(CutoffError):
                svc.confirm_cutoff(middle.id, reading_value=reading,
                                   reason='Observed on meter', actor_id=actor, now=_dt(12))
        assert svc.confirm_cutoff(middle.id, reading_value='150',
                                  reason='Observed on meter', actor_id=actor, now=_dt(12)).status == 'CONFIRMED'


def test_p07_handover_reasons_copied_into_correction(make_session):
    from tests.test_lifecycle import message
    with make_session() as db:
        room, a, b = uuid4(), uuid4(), uuid4()
        instant='2026-11-11T12:00:00+00:00'
        svc=MeteringService(db)
        svc.process_contract_event(message('ContractEnded',a,room,instant), now=_dt(12))
        svc.process_contract_event(message('ContractStarted',b,room,instant), now=_dt(12))
        cutoff = next(x for x in db.scalars(select(m.MeterCutoff)) if x.meter.meter_type == 'ELECTRICITY')
        assert len(repo.cutoff_reasons(db, cutoff.id)) == 2
        svc.confirm_cutoff(cutoff.id, reading_value='40', reason='Manual handover index',
                           actor_id=uuid4(), now=_dt(12))
        revision = svc.revise_cutoff(cutoff.id, reading_value='41', reason='Incorrect handover value',
                                    actor_id=uuid4(), now=_dt(12))
        assert {(r.contract_id, r.reason_type) for r in repo.cutoff_reasons(db, revision.id)} == {
            (a, 'CONTRACT_END'), (b, 'CONTRACT_START')}
        assert len(repo.cutoff_reasons(db, cutoff.id)) == 2


def test_p07_monthly_vietnam_00_idempotent(make_session):
    with make_session() as db:
        meter = new_meter(db)
        meter.created_at = datetime(2026, 9, 15, tzinfo=timezone.utc)
        db.flush()
        svc = MeteringService(db)
        at = datetime(2026, 11, 2, tzinfo=timezone.utc)
        expected = datetime(2026, 10, 31, 17, tzinfo=timezone.utc)
        assert svc.create_monthly_cutoffs(now=at) == 2  # Oct 1 and Nov 1 VN
        assert svc.create_monthly_cutoffs(now=at) == 0
        rows=list(db.scalars(select(m.MeterCutoff)))
        assert len(rows) == 2
        assert any(row.cutoff_at.replace(tzinfo=timezone.utc) == expected for row in rows)
        assert all(row.status == 'PENDING' for row in rows)
        assert svc.finalize_due_cutoffs(now=at) == 0
        assert all(row.status == 'PENDING' for row in rows)


def test_p07_offline_open_once_resolved_by_mqtt_duplicate(make_session):
    with make_session() as db:
        meter = new_meter(db)
        meter.created_at = _dt(10, 12)
        db.flush()
        svc = MeteringService(db)
        now = _dt(11, 12)
        assert svc.scan_offline(now=now) == 1
        assert svc.scan_offline(now=now) == 0
        alarm=repo.open_offline(db,meter.id)
        assert alarm is not None and alarm.status == 'OPEN'
        msg = sample(meter.id, stamp='2026-11-11T12:00:00Z', val='500')
        assert svc.record_telemetry(msg, now=now) == 'inserted'
        assert alarm.status == 'RESOLVED'
        # Duplicate QoS1 delivery still counts as a recent heartbeat.
        assert svc.record_telemetry(msg, now=now + timedelta(minutes=2)) == 'duplicate'
        assert svc.scan_offline(now=now + timedelta(minutes=19)) == 0
        assert svc.scan_offline(now=now + timedelta(minutes=23)) == 1
        assert repo.open_offline(db,meter.id) is not None


def test_p07_job_two_runs_no_duplicate_cutoff(make_session):
    with make_session() as db:
        meter = new_meter(db)
        meter.created_at = _dt(1)
        db.flush()
        svc = MeteringService(db)
        # first month boundary after creation -> Dec 1 (Nov 30 at 17:00 UTC)
        now = datetime(2026, 12, 1, 18, tzinfo=timezone.utc)
        boundary = datetime(2026, 11, 30, 17, tzinfo=timezone.utc)
        _insert_reading(db, meter.id, boundary - timedelta(minutes=5), '600')
        first = svc.run_cutoff_jobs(now=now)
        second = svc.run_cutoff_jobs(now=now)
        assert first['monthly_created'] == 1 and first['auto_confirmed'] == 1
        assert second['monthly_created'] == 0 and second['auto_confirmed'] == 0
        rows=list(db.scalars(select(m.MeterCutoff)))
        assert len(rows) == 1 and rows[0].reading_value == 600
        assert rows[0].status == 'CONFIRMED'


def test_p07_late_better_reading_alert_does_not_rewrite_confirmed(make_session):
    with make_session() as db:
        meter = new_meter(db)
        instant = _dt(11,12)
        row = _pending(db, meter.id, instant)
        _insert_reading(db, meter.id, instant - timedelta(minutes=10), '100')
        svc = MeteringService(db)
        assert svc.finalize_due_cutoffs(now=instant+timedelta(minutes=16))==1
        assert row.reading_value==100
        later = instant + timedelta(minutes=1)
        assert svc.record_telemetry(sample(meter.id, later.isoformat(), '101'),
                                    now=instant+timedelta(minutes=20))=='inserted'
        assert row.reading_value==100 and row.status=='CONFIRMED'
        alerts, n=svc.alerts_for_meter(meter.id)
        assert n==1 and alerts[0].alert_type=='LATE_AFTER_CUTOFF'
        assert alerts[0].related_cutoff_id==row.id
        assert svc.record_telemetry(sample(meter.id,later.isoformat(),'101'),
                                    now=instant+timedelta(minutes=21))=='duplicate'
        assert svc.alerts_for_meter(meter.id)[1]==1
        resolved=svc.resolve_meter_alert(alerts[0].id,note='Confirmed late telemetry review')
        assert resolved.status=='RESOLVED'


def test_p07_monthly_reuses_handover_same_instant_and_preserves_reasons(make_session):
    from tests.test_lifecycle import message
    from app.cutoffs import VN
    with make_session() as db:
        room, cid = uuid4(), uuid4()
        boundary = datetime(2026, 11, 30, 17, tzinfo=timezone.utc)  # Dec 1 in VN
        svc=MeteringService(db)
        # Room created weeks before the month boundary.
        repo.ensure_meter(db,room,'ELECTRICITY')
        repo.ensure_meter(db,room,'WATER')
        meters=repo.meters_for_room(db,room)
        for meter in meters:
            meter.created_at = _dt(1)
        db.flush()
        assert svc.process_contract_event(message('ContractStarted', cid, room,
            boundary.isoformat()), now=datetime(2026,12,2,tzinfo=timezone.utc))
        assert svc.create_monthly_cutoffs(now=datetime(2026,12,2,tzinfo=timezone.utc)) == 0
        cutoffs=list(db.scalars(select(m.MeterCutoff)))
        assert len(cutoffs)==2
        assert all(c.cutoff_type=='CONTRACT_START' for c in cutoffs)
        assert all(len(repo.cutoff_reasons(db,c.id))==1 for c in cutoffs)


def test_p07_late_contract_start_does_not_rewrite_confirmed_end(make_session):
    from tests.test_lifecycle import message
    with make_session() as db:
        room, previous, following = uuid4(),uuid4(),uuid4()
        instant = _dt(11,12).isoformat()
        svc=MeteringService(db)
        svc.process_contract_event(message('ContractEnded', previous, room, instant), now=_dt(12))
        first = next(c for c in db.scalars(select(m.MeterCutoff))
                     if c.meter.meter_type=='ELECTRICITY')
        svc.confirm_cutoff(first.id, reading_value='120', reason='Handover counter photographed',
                           actor_id=uuid4(), now=_dt(12))
        svc.process_contract_event(message('ContractStarted', following, room, instant), now=_dt(12))
        assert first.cutoff_type=='CONTRACT_END'
        assert first.status=='CONFIRMED'
        assert len(repo.cutoff_reasons(db,first.id))==2

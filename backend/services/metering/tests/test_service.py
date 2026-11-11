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

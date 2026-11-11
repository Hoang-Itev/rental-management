"""Real SQLite ORM for fast unit/API tests; PostgreSQL-specific behavior tested separately."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.config import RoomSettings, get_settings
from app.db import Base, get_db
from app.main import app
from app.service import RoomService
from app import schemas as s


@compiles(JSONB, "sqlite")
def compile_jsonb_for_test(element, compiler, **kw):
    return "JSON"


@pytest.fixture
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk_on(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def make_session(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
def client(make_session):
    def session_override():
        with make_session() as session:
            yield session
    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_settings] = lambda: RoomSettings(SERVICE_TOKEN="a" * 32)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def tree(make_session):
    with make_session() as db:
        svc = RoomService(db)
        prop = svc.create_property(s.PropertyCreate(name="Khu A", address="1 Demo Street"))
        building = svc.create_building(prop.id, s.BuildingCreate(name="Day A"))
        floor = svc.create_floor(building.id, s.FloorCreate(floor_number=1, name="Tang mot"))
        return {"property": prop.id, "building": building.id, "floor": floor.id}


@pytest.fixture
def test_service(make_session):
    with make_session() as db:
        yield RoomService(db)


def unit_room(code="A101", property_id=None):
    return s.RoomCreateItem(room_code=code, area_m2="22.50", listed_rent=2500000, property_id=property_id)

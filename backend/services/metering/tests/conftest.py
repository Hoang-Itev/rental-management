"""P03 Metering isolated SQLAlchemy SQLite tests; real PostgreSQL in integration."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import MeteringSettings, get_settings
from app.db import Base, get_db
from app.main import app
from app import models


@compiles(JSONB, "sqlite")
def compile_jsonb_for_test(element, compiler, **kw):
    return "JSON"


@pytest.fixture
def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # The original P03 model defines this PostgreSQL partial unique index.
    # SQLite would otherwise interpret it as a global UNIQUE(meter_id),
    # incorrectly prohibiting multiple non-OFFLINE alerts in unit tests.
    for idx in models.MeterAlert.__table__.indexes:
        if idx.name == "uq_meter_alerts_open_offline":
            idx.dialect_options["sqlite"]["where"] = text("status = 'OPEN' AND alert_type = 'OFFLINE'")
    # PostgreSQL uses an active-version partial UNIQUE index for cutoffs;
    # SQLite unit tests must match the predicate to permit revisions.
    for idx in models.MeterCutoff.__table__.indexes:
        if idx.name == "uq_meter_cutoffs_active_scope":
            idx.dialect_options["sqlite"]["where"] = text("status <> 'SUPERSEDED'")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    yield maker
    engine.dispose()


@pytest.fixture
def client(make_session):
    def db_override():
        with make_session() as session:
            yield session
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_settings] = lambda: MeteringSettings(SERVICE_TOKEN="s" * 32)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

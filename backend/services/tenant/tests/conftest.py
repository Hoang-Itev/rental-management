"""SQLite service/API tests; GiST exclusion is separately tested on real PostgreSQL."""
from __future__ import annotations
from uuid import UUID,uuid4
import pytest
from sqlalchemy import create_engine,event,text
from sqlalchemy.dialects.postgresql import JSONB,ExcludeConstraint
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session,sessionmaker
from sqlalchemy.pool import StaticPool
from app import models as m,schemas as s
from app.db import Base,get_db
from app.config import TenantSettings,get_settings
from app.clients import RoomUnavailable
from app.main import app

@compiles(JSONB,'sqlite')
def compile_jsonb(element,compiler,**kw):return 'JSON'

@pytest.fixture
def sessions():
    engine=create_engine('sqlite+pysqlite:///:memory:',poolclass=StaticPool,connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def fk_pragma(dbapi,record):dbapi.execute('PRAGMA foreign_keys=ON')
    # SQLite has no PostgreSQL GiST EXCLUDE. These constraints remain in production PostgreSQL.
    excluded=[]
    for table in Base.metadata.tables.values():
        for constraint in list(table.constraints):
            if isinstance(constraint,ExcludeConstraint):
                table.constraints.remove(constraint)
                excluded.append((table,constraint))
    old_default=m.ContractEvent.__table__.c.details.server_default
    m.ContractEvent.__table__.c.details.server_default=None
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    finally:
        engine.dispose()
        m.ContractEvent.__table__.c.details.server_default=old_default
        for table,constraint in excluded:table.append_constraint(constraint)

class FakeRoom:
    def __init__(self):self.available={};self.down=False
    def validate(self,room_id):
        if self.down:raise RoomUnavailable('down')
        return s.RoomValidation(room_id=room_id,exists=room_id in self.available,
           operational=self.available.get(room_id,False),room_code='A101' if room_id in self.available else None)

@pytest.fixture
def room():return FakeRoom()

@pytest.fixture
def env(sessions,room):
    from app.service import TenantService
    def svc():
        db=sessions()
        return TenantService(db,room)
    return svc

@pytest.fixture
def tenant_payload():return s.TenantCreate(full_name='Nguyen Van A',email='a@example.com',phone='0900000000')

@pytest.fixture
def make_contract():
    def factory(tenant_id,room_id,start='2026-12-01',end='2027-01-31',code=None,
                term_end=None):
        return s.ContractCreate(contract_code=code or 'CT'+uuid4().hex[:16],
          representative_tenant_id=tenant_id,room_id=room_id,
          start_date=start,end_date=end,initial_terms=s.TermInput(effective_from=start,
          effective_to=term_end,monthly_rent=2400000,electricity_unit_price=3500,water_unit_price=18000))
    return factory

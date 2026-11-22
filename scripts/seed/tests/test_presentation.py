"""Presentation fixture checks; SQLite validates ORM writes, not PostgreSQL-specific guards."""
import os
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parents[1]
ROOT = SEED.parents[1]
sys.path.insert(0,str(SEED))
import seed_service as seed
from presentation import RECIPIENTS, build_dataset, cutoff_plan, meter_value


@pytest.mark.parametrize('day', ['2026-11-22','2027-01-01','2028-03-01','2028-03-22'])
def test_demo_dates_inventory_and_all_recipients(day):
    data = build_dataset(date.fromisoformat(day))
    assert len(data['rooms']) == len(set(data['rooms'])) == 20
    assert len(data['contracts']) == 16 and len(data['occupied_rooms']) == 15
    emails = Counter(data['tenants'][c['tenant_index']]['email'] for c in data['contracts']
                     if c['room_code'] in data['issued_rooms'])
    assert emails == Counter({email:3 for email in RECIPIENTS})
    assert data['billing_month'] < data['period_end'] <= data['issued_day'] < data['invoice_due_date'] < day
    assert date.fromisoformat(data['invoice_due_date']) - date.fromisoformat(data['issued_day']) == timedelta(days=10)
    assert sum(p['pending'] for room in data['rooms'] for p in cutoff_plan(room,data))*2 == 6
    final = next(c for c in data['contracts'] if c['status']=='ENDED')
    assert final['start_date'] <= final['actual_end_date'] < day
    for code in data['issued_rooms']:
        for kind in ('ELECTRICITY','WATER'):
            first,last = (meter_value(code,kind,date.fromisoformat(data[key]),data) for key in ('billing_month','period_end'))
            assert last-first == seed.delta_meter_value(code,kind,data)


# Separate interpreters preserve database-per-service ORM registries named app.*.
ORM_CHECK = '''
import os, uuid
from datetime import date, datetime, timezone
from sqlalchemy import create_engine, event, select, func, text
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from app import models as m
from app.db import Base
import seed_service as seed
import presentation as demo
from verify_presentation import check_presentation
@compiles(JSONB,'sqlite')
def jsonb(*args,**kwargs): return 'JSON'
for table in Base.metadata.tables.values():
    for column in table.columns:
        if column.server_default is not None and "::jsonb" in str(column.server_default.arg):
            column.server_default.arg = text("'{}'")
    for constraint in list(table.constraints):
        if isinstance(constraint,ExcludeConstraint):
            table.constraints.remove(constraint)
    for index in table.indexes:
        predicate=index.dialect_options['postgresql'].get('where')
        if predicate is not None: index.dialect_options['sqlite']['where']=predicate
engine=create_engine('sqlite:///:memory:')
@event.listens_for(engine,'connect')
def setup(conn, _):
    conn.execute('PRAGMA foreign_keys=ON')
    conn.create_function('gen_random_uuid',0,lambda:uuid.uuid4().hex)
Base.metadata.create_all(engine)
sessions=sessionmaker(bind=engine,expire_on_commit=False)
service=os.environ['CHECK_SERVICE']
data=seed.dataset()
fn={'auth':seed.seed_auth,'room':seed.seed_room,'tenant':seed.seed_tenant,
    'metering':demo.seed_metering,'billing':demo.seed_billing,'notification':seed.seed_notification}[service]
with sessions.begin() as db: fn(db,m,data)
with sessions.begin() as db: assert fn(db,m,data)==0, 'repeat seed must not insert rows'
with sessions() as db:
    if service=='auth':
        from pwdlib import PasswordHash
        owner=db.get(m.User,seed.sid('owner',os.environ['OWNER_EMAIL']))
        assert PasswordHash.recommended().verify(os.environ['SEED_OWNER_PASSWORD'],owner.password_hash)
    else: check_presentation(db,m,data,service)
if service=='billing':
    from app.schemas import AccessLinkRequest
    from app.service import create_access_link, read_access_link
    from app.config import Settings
    with sessions.begin() as db: assert demo.queue_reminders(db,m,data)==12
    with sessions.begin() as db: assert demo.queue_reminders(db,m,data)==0
    with sessions() as db:
        events=db.scalars(select(m.OutboxEvent)).all()
        event_id,invoice_id,email=events[0].id,events[0].aggregate_id,events[0].payload['data']['recipient_email']
        assert all(e.event_type=='InvoiceReminderRequested' for e in events)
    with sessions() as db:
        link=create_access_link(db,invoice_id,AccessLinkRequest(source_event_id=event_id,recipient_email=email),
                               Settings(service_token='s'*32))
        assert '/hoa-don-cong-khai/' in link.url
    with sessions() as db:
        view=read_access_link(db,link.url.rsplit('/',1)[1])
        assert view.status=='ISSUED' and view.total_amount>0
if service=='metering':
    from app.service import MeteringService
    with sessions.begin() as db:
        # Existing intentionally missing boundaries must stay pending after automatic selection.
        assert MeteringService(db).finalize_due_cutoffs(now=datetime.now(timezone.utc))==0
    for code in data['blocked_rooms']+[data['final_room']]:
        for plan in demo.cutoff_plan(code,data):
            if plan['pending']:
                for kind in ('ELECTRICITY','WATER'):
                    with sessions() as db:
                        row=MeteringService(db).confirm_cutoff(
                            seed.sid('cutoff',f'{code}:{kind}:{plan["day"].isoformat()}'),
                            reading_value=demo.meter_value(code,kind,plan['day'],data),
                            reason='Demo handover verification', actor_id=uuid.uuid4())
                        assert row.status=='CONFIRMED'
print('PASS',service)
'''


@pytest.mark.parametrize('service', seed.VALID_SERVICES)
def test_presentation_orm_roundtrip_idempotence_and_reminder_links(service):
    pytest.importorskip('sqlalchemy')
    pytest.importorskip('pydantic_settings')
    pytest.importorskip('pwdlib')
    app_root = ROOT/'backend'/('auth' if service=='auth' else 'services/'+service)
    env = {**os.environ,'PYTHONPATH':os.pathsep.join((str(app_root),str(SEED))),
           'SEED_PROFILE':'presentation','SEED_AS_OF':date.today().isoformat(),
           'CHECK_SERVICE':service,'OWNER_EMAIL':'hoangdv955@gmail.com','SEED_OWNER_PASSWORD':'123456789011'}
    result=subprocess.run([sys.executable,'-c',ORM_CHECK],env=env,text=True,capture_output=True)
    assert result.returncode==0, result.stdout+result.stderr

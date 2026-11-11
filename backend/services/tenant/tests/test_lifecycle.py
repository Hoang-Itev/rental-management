"""P05 lifecycle tests; real broker and PostgreSQL integration is separate."""
from datetime import datetime, timezone, date
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select,func
from app import models as m, schemas as s
from app.service import TenantError, TenantService
from app.scheduler import run_due


def act(env,method,*args,**kw):
    svc=env()
    try:return getattr(svc,method)(*args,**kw)
    finally:svc.db.close()


def setup(env,room,make_contract):
    payer=act(env,'create_tenant',s.TenantCreate(full_name='P05 Payer',email='p05@example.org'))
    rid=uuid4();room.available[rid]=True
    draft=act(env,'create_contract',make_contract(payer.id,rid,start='2026-11-01',end='2026-11-15'))
    act(env,'confirm',draft.id)
    return payer,rid,draft


def now(day):return datetime.fromisoformat(day+'T00:00:00+07:00')


def error(fn):
    with pytest.raises(TenantError) as e:fn()
    assert e.value.status==409


def test_activation_only_after_start_and_outbox_once(env,room,make_contract,sessions):
    payer,rid,draft=setup(env,room,make_contract)
    error(lambda:act(env,'activate',draft.id,now=now('2026-10-31')))
    assert act(env,'contract',draft.id).status=='SCHEDULED'
    act(env,'activate',draft.id,now=now('2026-11-01'))
    act(env,'activate',draft.id,now=now('2026-11-02'))
    with sessions() as db:
        rows=list(db.scalars(select(m.OutboxEvent)))
        assert len(rows)==1 and rows[0].event_type=='ContractStarted'
        assert rows[0].payload['effective_at']=='2026-11-01T00:00:00+07:00'
    assert [x.event_type for x in act(env,'events',draft.id)].count('STARTED')==1


def test_cannot_activate_when_physically_occupied(env,room,make_contract):
    payer,rid,c=setup(env,room,make_contract)
    other=uuid4()
    room.available[rid]=True
    room.occupancy={rid:other}  # FakeRoom's simple mock has default None, see monkeypatch below.
    original=room.validate
    def occupied(room_id):
        reply=original(room_id)
        return reply.model_copy(update={'occupancy_contract_id':other})
    room.validate=occupied
    error(lambda:act(env,'activate',c.id,now=now('2026-11-01')))
    assert act(env,'contract',c.id).status=='SCHEDULED'


def test_scheduler_expired_pending_does_not_release_room(env,room,make_contract,sessions):
    _,rid,c=setup(env,room,make_contract)
    act(env,'activate',c.id,now=now('2026-11-01'))
    act(env,'mark_expired',c.id,now=now('2026-11-16'))
    assert act(env,'contract',c.id).status=='EXPIRED_PENDING'
    with sessions() as db:
        assert [x.event_type for x in db.scalars(select(m.OutboxEvent))]==['ContractStarted']


def test_end_after_expiry_supports_late_handover(env,room,make_contract,sessions):
    _,rid,c=setup(env,room,make_contract)
    act(env,'activate',c.id,now=now('2026-11-01'))
    act(env,'mark_expired',c.id,now=now('2026-11-16'))
    ended=act(env,'end_contract',c.id,date(2026,11,20),'Moved out',now=now('2026-11-21'))
    assert ended.status=='ENDED' and ended.actual_end_date==date(2026,11,20)
    assert act(env,'end_contract',c.id,date(2026,11,20),'Moved out',now=now('2026-11-21')).id==c.id
    with sessions() as db:
        events=list(db.scalars(select(m.OutboxEvent).order_by(m.OutboxEvent.created_at)))
        assert sorted(x.event_type for x in events)==['ContractEnded','ContractStarted']
        assert next(x for x in events if x.event_type=='ContractEnded').payload['effective_at']=='2026-11-21T00:00:00+07:00'


def test_renew_no_overlap_preserves_prices(env,room,make_contract):
    _,rid,c=setup(env,room,make_contract)
    result=act(env,'renew',c.id,date(2026,12,15),'extend')
    assert result.end_date==date(2026,12,15)
    assert len(act(env,'terms',c.id))==1
    assert [x.event_type for x in act(env,'events',c.id)][-1]=='EXTENDED'
    error(lambda:act(env,'renew',c.id,date(2026,12,1),'shorten'))


def test_renew_price_version_on_boundary(env,room,make_contract):
    _,rid,c=setup(env,room,make_contract)
    term=s.TermInput(effective_from='2026-11-16',monthly_rent=3000000,electricity_unit_price=4000,water_unit_price=18000)
    act(env,'renew',c.id,date(2026,12,15),new_terms=term)
    terms=act(env,'terms',c.id)
    assert [x.effective_from for x in terms]==[date(2026,11,1),date(2026,11,16)]
    assert terms[0].effective_to==date(2026,11,16)


def test_job_applies_due_contract_without_early_start(env,room,make_contract,sessions):
    _,rid,c=setup(env,room,make_contract)
    before=run_due(now=now('2026-10-31'),sessions=sessions,room_factory=lambda:room)
    assert before['started']==0
    result=run_due(now=now('2026-11-01'),sessions=sessions,room_factory=lambda:room)
    assert result['started']==1
    result=run_due(now=now('2026-11-16'),sessions=sessions,room_factory=lambda:room)
    assert result['pending_end']==1

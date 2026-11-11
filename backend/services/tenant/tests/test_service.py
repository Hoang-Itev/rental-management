from __future__ import annotations
from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from app import models as m,schemas as s
from app.service import TenantError


def act(env,method,*args,**kw):
    svc=env()
    try:return getattr(svc,method)(*args,**kw)
    finally:svc.db.close()

def seeded(env,room,tenant_payload,make_contract,**kw):
    payer=act(env,'create_tenant',tenant_payload)
    rid=uuid4();room.available[rid]=kw.pop('operational',True)
    created=act(env,'create_contract',make_contract(payer.id,rid,**kw))
    return payer,rid,created

def err(code, fn):
    with pytest.raises(TenantError) as e:fn()
    assert e.value.status==code


def test_tenant_crud_and_pagination(env,tenant_payload):
    first=act(env,'create_tenant',tenant_payload)
    assert first.full_name=='Nguyen Van A'
    assert act(env,'tenant',first.id).email=='a@example.com'
    patched=act(env,'patch_tenant',first.id,s.TenantPatch(full_name='B',phone=None))
    assert patched.full_name=='B' and patched.phone is None
    rows,count=act(env,'tenants',1,20)
    assert count==1 and rows[0].id==first.id
    err(404,lambda:act(env,'tenant',uuid4()))


def test_draft_creation_terms_and_history(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    assert draft.status=='DRAFT' and draft.room_code_snapshot=='A101'
    assert draft.deposit_amount is None
    terms=act(env,'terms',draft.id)
    assert len(terms)==1 and terms[0].monthly_rent==2400000 and terms[0].effective_to is None
    events=act(env,'events',draft.id)
    assert [e.event_type for e in events]==['CREATED']
    assert act(env,'contracts',1,20,rid,'DRAFT')[1]==1
    assert act(env,'contracts',1,20,uuid4(),'DRAFT')[1]==0
    err(404,lambda:act(env,'terms',uuid4()))
    err(404,lambda:act(env,'events',uuid4()))


def test_draft_can_be_created_for_inactive_room_but_cannot_confirm(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract,operational=False)
    err(409,lambda:act(env,'confirm',draft.id))
    assert act(env,'contract',draft.id).status=='DRAFT'


def test_confirm_happy_path_and_retry(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    result=act(env,'confirm',draft.id)
    assert result.status=='SCHEDULED'
    assert act(env,'confirm',draft.id).status=='SCHEDULED'
    assert [e.event_type for e in act(env,'events',draft.id)]==['CREATED','CONFIRMED']
    err(409,lambda:act(env,'patch_contract',draft.id,s.ContractPatch(contract_code='C2')))
    err(409,lambda:act(env,'add_term',draft.id,s.TermInput(effective_from='2026-12-15',monthly_rent=3,electricity_unit_price=2,water_unit_price=1)))


def test_overlap_for_two_confirmed_contracts(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    second=act(env,'create_contract',make_contract(payer.id,rid,start='2027-01-31',end='2027-02-28'))
    act(env,'confirm',draft.id)
    err(409,lambda:act(env,'confirm',second.id))
    assert act(env,'contract',second.id).status=='DRAFT'


def test_no_overlap_adjacent_dates(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    second=act(env,'create_contract',make_contract(payer.id,rid,start='2027-02-01',end='2027-04-30'))
    assert act(env,'confirm',draft.id).status=='SCHEDULED'
    assert act(env,'confirm',second.id).status=='SCHEDULED'


def test_missing_room_and_upstream_down(env,room,tenant_payload,make_contract):
    payer=act(env,'create_tenant',tenant_payload)
    rid=uuid4()
    err(404,lambda:act(env,'create_contract',make_contract(payer.id,rid)))
    room.available[rid]=True
    room.down=True
    err(503,lambda:act(env,'create_contract',make_contract(payer.id,rid)))
    room.down=False
    draft=act(env,'create_contract',make_contract(payer.id,rid))
    room.down=True
    err(503,lambda:act(env,'confirm',draft.id))
    assert act(env,'contract',draft.id).status=='DRAFT'


def test_missing_tenant_and_contract(env,room,make_contract):
    rid=uuid4();room.available[rid]=True
    err(404,lambda:act(env,'create_contract',make_contract(uuid4(),rid)))
    err(404,lambda:act(env,'contract',uuid4()))
    err(404,lambda:act(env,'confirm',uuid4()))
    err(404,lambda:act(env,'patch_contract',uuid4(),s.ContractPatch(contract_code='x')))


def test_contract_draft_patch_and_term_repair(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract,term_end='2026-12-20')
    err(409,lambda:act(env,'confirm',draft.id))
    term=act(env,'add_term',draft.id,s.TermInput(effective_from='2026-12-20',monthly_rent=3000000,electricity_unit_price=4000,water_unit_price=20000,monthly_service_fee=50))
    assert term.monthly_rent==3000000
    assert [x.effective_to for x in act(env,'terms',draft.id)]==[date(2026,12,20),None]
    assert act(env,'confirm',draft.id).status=='SCHEDULED'


def test_contract_term_version_rules(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    x=lambda frm,to=None:s.TermInput(effective_from=frm,effective_to=to,monthly_rent=2,electricity_unit_price=1,water_unit_price=1)
    err(409,lambda:act(env,'add_term',draft.id,x('2026-12-01')))
    err(409,lambda:act(env,'add_term',draft.id,x('2027-02-01')))
    err(409,lambda:act(env,'add_term',draft.id,x('2027-01-01','2027-02-02')))
    act(env,'add_term',draft.id,x('2027-01-01'))
    err(409,lambda:act(env,'add_term',draft.id,x('2027-01-01')))
    assert act(env,'confirm',draft.id).status=='SCHEDULED'


def test_contract_patch_date_still_requires_terms_cover(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    act(env,'patch_contract',draft.id,s.ContractPatch(start_date='2026-12-02',end_date='2027-02-28'))
    err(409,lambda:act(env,'confirm',draft.id))
    err(409,lambda:act(env,'patch_contract',draft.id,s.ContractPatch(end_date='2026-11-30')))


def test_draft_invalid_payer_email(env,room,make_contract):
    payer=act(env,'create_tenant',s.TenantCreate(full_name='Missing email'))
    rid=uuid4();room.available[rid]=True
    draft=act(env,'create_contract',make_contract(payer.id,rid))
    err(409,lambda:act(env,'confirm',draft.id))
    act(env,'patch_tenant',payer.id,s.TenantPatch(email='payer@example.com'))
    assert act(env,'confirm',draft.id).status=='SCHEDULED'


def test_duplicate_contract_code_rolls_back(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract,code='EXISTS')
    another=uuid4();room.available[another]=True
    err(409,lambda:act(env,'create_contract',make_contract(payer.id,another,code='EXISTS')))
    assert act(env,'contracts')[1]==1
    assert len(act(env,'events',draft.id))==1


def test_schema_reject_invalid_dates_prices_and_nulls():
    with pytest.raises(ValueError):s.TermInput(effective_from='2026-01-20',effective_to='2026-01-20',monthly_rent=5,electricity_unit_price=1,water_unit_price=2)
    with pytest.raises(ValueError):s.TermInput(effective_from='2026-01-20',monthly_rent=-1,electricity_unit_price=1,water_unit_price=2)
    with pytest.raises(ValueError):s.ContractPatch()
    with pytest.raises(ValueError):s.ContractPatch(start_date=None)
    with pytest.raises(ValueError):s.TenantPatch(full_name=None)
    with pytest.raises(ValueError):s.TenantCreate(full_name='a',email='not-an-email')
    base={'contract_code':'x','room_id':str(uuid4()),'representative_tenant_id':str(uuid4()),
          'start_date':'2026-12-01','end_date':'2026-11-30',
          'initial_terms':{'effective_from':'2026-12-01','monthly_rent':5,'electricity_unit_price':1,'water_unit_price':1}}
    with pytest.raises(ValueError):s.ContractCreate(**base)
    base['end_date']='2027-01-01';base['initial_terms']['effective_from']='2026-12-02'
    with pytest.raises(ValueError):s.ContractCreate(**base)


def test_confirm_rejects_gap_after_manual_draft_edit(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract,term_end='2026-12-20')
    err(409,lambda:act(env,'add_term',draft.id,s.TermInput(effective_from='2026-12-21',monthly_rent=1,electricity_unit_price=2,water_unit_price=3)))
    err(409,lambda:act(env,'confirm',draft.id))


def test_draft_reject_confirm_when_room_turns_inactive(env,room,tenant_payload,make_contract):
    payer,rid,draft=seeded(env,room,tenant_payload,make_contract)
    room.available[rid]=False
    err(409,lambda:act(env,'confirm',draft.id))

"""Owner-only routes: Nginx auth_request validates JWT before proxying /api/v1."""
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from app import schemas as s
from app.clients import RoomClient
from app.config import TenantSettings, get_settings
from app.db import get_db
from app.service import TenantService

router=APIRouter(prefix='/api/v1',tags=['Tenant'])
Db=Annotated[Session, Depends(get_db)]
Settings=Annotated[TenantSettings, Depends(get_settings)]
Page=Annotated[int,Query(ge=1)]
Size=Annotated[int,Query(ge=1,le=100)]

def service(db: Session, settings:TenantSettings):
    return TenantService(db, RoomClient(settings))

def page_result(rows,total,page,size,model):
    return {'items':[model.model_validate(row) for row in rows],
            'meta': {'page':page,'page_size':size,'total':total}}

def actor_id(header: str | None):
    if not header: return None
    try: return UUID(header)
    except ValueError: return None

@router.get('/tenants',response_model=s.Page[s.TenantOut])
def tenants(db:Db,settings:Settings,page:Page=1,page_size:Size=20):
    rows,n=service(db,settings).tenants(page,page_size)
    return page_result(rows,n,page,page_size,s.TenantOut)

@router.post('/tenants',response_model=s.TenantOut,status_code=201)
def create_tenant(data:s.TenantCreate,db:Db,settings:Settings):
    return service(db,settings).create_tenant(data)

@router.get('/tenants/{tenant_id}',response_model=s.TenantOut)
def tenant(tenant_id:UUID,db:Db,settings:Settings):
    return service(db,settings).tenant(tenant_id)

@router.patch('/tenants/{tenant_id}',response_model=s.TenantOut)
def patch_tenant(tenant_id:UUID,data:s.TenantPatch,db:Db,settings:Settings):
    return service(db,settings).patch_tenant(tenant_id,data)

@router.get('/contracts',response_model=s.Page[s.ContractOut])
def contracts(db:Db,settings:Settings,page:Page=1,page_size:Size=20,
              room_id:UUID|None=None,status:s.Status|None=None):
    rows,n=service(db,settings).contracts(page,page_size,room_id,status)
    return page_result(rows,n,page,page_size,s.ContractOut)

@router.post('/contracts',response_model=s.ContractOut,status_code=201)
def create_contract(data:s.ContractCreate,db:Db,settings:Settings,
                    x_auth_user_id: Annotated[str|None,Header(alias='X-Auth-User-Id')]=None):
    return service(db,settings).create_contract(data,actor_id(x_auth_user_id))

@router.get('/contracts/{contract_id}',response_model=s.ContractOut)
def contract(contract_id:UUID,db:Db,settings:Settings):
    return service(db,settings).contract(contract_id)

@router.patch('/contracts/{contract_id}',response_model=s.ContractOut)
def patch_contract(contract_id:UUID,data:s.ContractPatch,db:Db,settings:Settings):
    return service(db,settings).patch_contract(contract_id,data)

@router.get('/contracts/{contract_id}/terms',response_model=s.Page[s.TermOut])
def terms(contract_id:UUID,db:Db,settings:Settings,page:Page=1,page_size:Size=20):
    rows=service(db,settings).terms(contract_id)
    return page_result(rows[(page-1)*page_size:page*page_size],len(rows),page,page_size,s.TermOut)

@router.post('/contracts/{contract_id}/terms',response_model=s.TermOut,status_code=201)
def add_term(contract_id:UUID,data:s.TermInput,db:Db,settings:Settings):
    return service(db,settings).add_term(contract_id,data)

@router.get('/contracts/{contract_id}/events',response_model=s.Page[s.ContractEventOut])
def events(contract_id:UUID,db:Db,settings:Settings,page:Page=1,page_size:Size=20):
    rows=service(db,settings).events(contract_id)
    return page_result(rows[(page-1)*page_size:page*page_size],len(rows),page,page_size,s.ContractEventOut)

@router.post('/contracts/{contract_id}/confirm',response_model=s.ContractOut)
def confirm(contract_id:UUID,db:Db,settings:Settings,
            x_auth_user_id: Annotated[str|None,Header(alias='X-Auth-User-Id')]=None):
    return service(db,settings).confirm(contract_id,actor_id(x_auth_user_id))


@router.post('/contracts/{contract_id}/renew', response_model=s.ContractOut)
def renew_contract(contract_id: UUID, body: s.RenewRequest, db: Db, settings: Settings):
    return service(db,settings).renew(contract_id, body.new_end_date, body.reason, body.new_terms)

@router.post('/contracts/{contract_id}/end', response_model=s.ContractOut)
def end_contract(contract_id: UUID, body: s.EndRequest, db: Db, settings: Settings,
                 x_auth_user_id: Annotated[str|None,Header(alias='X-Auth-User-Id')]=None):
    return service(db,settings).end_contract(contract_id, body.actual_end_date, body.reason, actor_id(x_auth_user_id))

@router.post('/jobs/contracts/lifecycle/run', response_model=s.LifecycleResult, status_code=202)
def run_contract_lifecycle(body: s.LifecycleRun, db: Db, settings: Settings):
    from app.scheduler import run_due
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if body.as_of is not None:
        if body.as_of.tzinfo is None or body.as_of > now:
            from app.service import invalid
            raise invalid('as_of must be timezone-aware and not in the future')
        now = body.as_of
    return run_due(now=now, sessions=__import__('app.db',fromlist=['get_sessionmaker']).get_sessionmaker(),
                   room_factory=lambda: RoomClient(settings))

"""Private contract read API for later Billing integration, never Nginx-public."""
from __future__ import annotations
from secrets import compare_digest
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app import schemas as s
from app.clients import RoomClient
from app.config import TenantSettings, get_settings
from app.db import get_db
from app.service import TenantService

router=APIRouter(prefix='/internal/v1',tags=['Internal-Tenant'],include_in_schema=False)

def credentials(x_service_token,settings):
    if x_service_token is None or not compare_digest(x_service_token,settings.service_token):
        raise HTTPException(status_code=403,detail='internal_only')

@router.get('/contracts/{contract_id}')
def internal_contract(contract_id:UUID,
                      db:Annotated[Session,Depends(get_db)],
                      settings:Annotated[TenantSettings,Depends(get_settings)],
                      x_service_token:Annotated[str|None,Header(alias='X-Service-Token')]=None):
    credentials(x_service_token,settings)
    svc=TenantService(db,RoomClient(settings))
    contract=svc.contract(contract_id)
    terms=svc.terms(contract_id)
    tenant=svc.tenant(contract.representative_tenant_id)
    return {'contract':s.ContractOut.model_validate(contract),
            'terms':[s.TermOut.model_validate(t) for t in terms],
            'payer':{'id':str(tenant.id),'full_name':tenant.full_name,'email':tenant.email}}

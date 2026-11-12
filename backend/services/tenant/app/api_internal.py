"""Private contract read API for later Billing integration, never Nginx-public."""
from __future__ import annotations
from datetime import date, timedelta
from secrets import compare_digest
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from app.models import Contract
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

@router.get('/contracts/billable')
def billable_contracts(
    period_start: date, period_end_exclusive: date,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[TenantSettings, Depends(get_settings)],
    x_service_token: Annotated[str | None, Header(alias='X-Service-Token')] = None,
    cursor: UUID | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    credentials(x_service_token, settings)
    if period_end_exclusive <= period_start:
        raise HTTPException(422, detail='Invalid billing period')
    conditions = [
        Contract.status.in_(('ACTIVE', 'EXPIRED_PENDING', 'ENDED')),
        Contract.start_date < period_end_exclusive,
        func.least(Contract.end_date, func.coalesce(
            Contract.actual_end_date, Contract.end_date)) >= period_start,
    ]
    if cursor is not None:
        conditions.append(Contract.id > cursor)
    rows = list(db.scalars(select(Contract).where(*conditions).order_by(Contract.id).limit(limit + 1)))
    result = {'items': [
        {'contract_id': row.id, 'room_id': row.room_id, 'status': row.status,
         'start_date': row.start_date, 'end_date': row.end_date,
         'actual_end_date': row.actual_end_date}
        for row in rows[:limit]
    ]}
    if len(rows) > limit:
        result['next_cursor'] = rows[limit - 1].id
    return result


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


@router.get('/contracts/{contract_id}/billing-context')
def billing_context(
    contract_id: UUID, db: Annotated[Session, Depends(get_db)],
    settings: Annotated[TenantSettings, Depends(get_settings)],
    x_service_token: Annotated[str | None, Header(alias='X-Service-Token')] = None,
):
    credentials(x_service_token, settings)
    svc = TenantService(db, RoomClient(settings))
    contract = svc.contract(contract_id)
    payer = svc.tenant(contract.representative_tenant_id)
    last_day = min(contract.end_date, contract.actual_end_date or contract.end_date)
    if last_day == date.max:
        raise HTTPException(422, detail='Unsupported contract end date')
    return {
        'contract_id': contract.id, 'room_id': contract.room_id,
        'contract_status': contract.status, 'tenant_name': payer.full_name,
        'tenant_email': payer.email, 'room_code': contract.room_code_snapshot,
        'chargeable_from': contract.start_date,
        'chargeable_to_exclusive': last_day + timedelta(days=1),
        'terms': [s.TermOut.model_validate(term).model_dump(exclude={'contract_id'})
                  for term in svc.terms(contract_id)],
    }


@router.get('/contracts/{contract_id}/expiry-notification-eligibility')
def expiry_notification_eligibility(
    contract_id: UUID, end_date: date,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[TenantSettings, Depends(get_settings)],
    x_service_token: Annotated[str | None, Header(alias='X-Service-Token')] = None,
):
    from datetime import datetime
    from app.service import VN

    credentials(x_service_token, settings)
    contract = db.get(Contract, contract_id)
    today = datetime.now(VN).date()
    eligible = bool(
        contract and contract.status == 'ACTIVE' and contract.actual_end_date is None
        and contract.end_date == end_date and end_date >= today
    )
    return {'contract_id': contract_id, 'end_date': end_date, 'eligible': eligible}

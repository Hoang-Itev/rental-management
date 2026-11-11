"""Owner-only read endpoints; existing Nginx /api/v1/meters routes require JWT."""
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from datetime import datetime, timezone, timedelta
from pydantic import AwareDatetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import ReadingOut, MeterAlertOut
from app.service import MeteringService
from app.telemetry import UnknownMeter

router = APIRouter(prefix='/api/v1/meters', tags=['Metering'])
Db = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]

@router.get('/{meter_id}/readings')
def readings(meter_id: UUID, db: Db, page: Page = 1, page_size: Size = 100,
             from_at: AwareDatetime | None = Query(default=None, alias='from'),
             to_at: AwareDatetime | None = Query(default=None, alias='to')):
    try:
        rows, total = MeteringService(db).readings_for_meter(meter_id, page=page, page_size=page_size,
                                                              from_at=from_at, to_at=to_at)
    except UnknownMeter as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'items': [ReadingOut.model_validate(x).model_dump(mode='json') for x in rows],
            'meta': {'page': page, 'page_size': page_size, 'total': total}}

@router.get('/{meter_id}/alerts')
def alerts(meter_id: UUID, db: Db, page: Page = 1, page_size: Size = 100):
    try:
        rows, total = MeteringService(db).alerts_for_meter(meter_id, page=page, page_size=page_size)
    except UnknownMeter as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'items': [MeterAlertOut.model_validate(x).model_dump(mode='json') for x in rows],
            'meta': {'page': page, 'page_size': page_size, 'total': total}}


# Canonical OpenAPI global alert listing, in addition to the per-meter convenience route.
alerts_router = APIRouter(prefix='/api/v1', tags=['Metering'])

@alerts_router.get('/meter-alerts')
def all_alerts(db: Db, page: Page = 1, page_size: Size = 100,
               status: str | None = Query(default=None, pattern='^(OPEN|RESOLVED)$'),
               alert_type: str | None = Query(default=None, pattern='^(OFFLINE|READING_DECREASE|LATE_AFTER_CUTOFF|CONFLICTING_DUPLICATE)$')):
    rows, total = MeteringService(db).list_alerts(status=status, alert_type=alert_type,
                                                  page=page, page_size=page_size)
    return {'items': [MeterAlertOut.model_validate(x).model_dump(mode='json') for x in rows],
            'meta': {'page':page, 'page_size':page_size, 'total':total}}


# P07 cutoff endpoints. X-Auth-User-Id is supplied by Nginx from verified JWT.
# The service is private on Docker's network, never directly published.
from datetime import timezone
from app.schemas import ManualCutoffInput, CutoffOut, CutoffReasonOut, JobResult, MonthlyRunInput
from app.cutoffs import CutoffError
from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

cutoff_router = APIRouter(prefix='/api/v1/meter-cutoffs', tags=['Meter cutoffs'])
job_router = APIRouter(prefix='/api/v1/jobs/meters', tags=['Meter cutoff jobs'])


def cutoff_payload(db: Session, cutoff):
    svc = MeteringService(db)
    obj = CutoffOut.model_validate(cutoff).model_dump(mode='json')
    obj['reasons'] = [CutoffReasonOut.model_validate(r).model_dump(mode='json')
                      for r in svc.cutoff_reasons(cutoff.id)]
    return obj


def cutoff_error(exc: CutoffError):
    raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@cutoff_router.get('')
def list_cutoffs(db: Db, meter_id: UUID | None = None, room_id: UUID | None = None,
                 status: str | None = Query(default=None, pattern='^(PENDING|CONFIRMED|SUPERSEDED)$'),
                 cutoff_type: str | None = Query(default=None, pattern='^(MONTHLY|CONTRACT_START|CONTRACT_END)$'),
                 from_at: AwareDatetime | None = Query(default=None, alias='from'),
                 to_at: AwareDatetime | None = Query(default=None, alias='to'),
                 page: Page = 1, page_size: Size = 100):
    if from_at is not None and to_at is not None and from_at >= to_at:
        raise HTTPException(status_code=422, detail='to must be after from (exclusive)')
    rows, count = MeteringService(db).list_cutoffs(
        meter_id=meter_id, room_id=room_id, status=status, cutoff_type=cutoff_type,
        from_at=from_at, to_at=to_at, page=page, page_size=page_size)
    return {'items': [cutoff_payload(db, x) for x in rows],
            'meta': {'page': page, 'page_size': page_size, 'total': count}}


@cutoff_router.get('/{cutoff_id}')
def get_cutoff(cutoff_id: UUID, db: Db):
    try:
        cutoff = MeteringService(db).cutoff(cutoff_id)
    except CutoffError as exc:
        cutoff_error(exc)
    return cutoff_payload(db, cutoff)


@cutoff_router.post('/{cutoff_id}/confirm')
def confirm_cutoff(cutoff_id: UUID, body: ManualCutoffInput, db: Db,
                   actor: UUID = Header(alias='X-Auth-User-Id')):
    try:
        row = MeteringService(db).confirm_cutoff(
            cutoff_id, reading_value=body.reading_value, reason=body.manual_reason, actor_id=actor)
    except CutoffError as exc:
        cutoff_error(exc)
    return cutoff_payload(db, row)


@cutoff_router.post('/{cutoff_id}/revise', status_code=201, include_in_schema=False)
@cutoff_router.post('/{cutoff_id}/corrections', status_code=201)
def revise_cutoff(cutoff_id: UUID, body: ManualCutoffInput, db: Db,
                  actor: UUID = Header(alias='X-Auth-User-Id')):
    try:
        row = MeteringService(db).revise_cutoff(
            cutoff_id, reading_value=body.reading_value, reason=body.manual_reason, actor_id=actor)
    except CutoffError as exc:
        cutoff_error(exc)
    return cutoff_payload(db, row)


@job_router.post('/cutoffs', response_model=JobResult)
def run_cutoff_job(db: Db):
    # Optional manual trigger. Same idempotent code as the separate scheduler.
    try:
        return MeteringService(db).run_cutoff_jobs()
    except CutoffError as exc:
        cutoff_error(exc)


@router.get('/{meter_id}/cutoffs')
def cutoffs_for_meter(meter_id: UUID, db: Db, page: Page = 1, page_size: Size = 100):
    from app import models as m
    if db.get(m.Meter, meter_id) is None:
        raise HTTPException(status_code=404, detail='Meter not found')
    rows, count = MeteringService(db).list_cutoffs(meter_id=meter_id,
                                                    page=page, page_size=page_size)
    return {'items': [cutoff_payload(db, row) for row in rows],
            'meta': {'page':page, 'page_size':page_size, 'total':count}}


@job_router.post('/monthly-cutoffs/run', status_code=202)
def monthly_cutoff_run(body: MonthlyRunInput, db: Db):
    """Explicit month-boundary demo job; same transactional logic as scheduler."""
    from uuid import uuid4
    from app.cutoffs import utc
    now = datetime.now(timezone.utc)
    svc = MeteringService(db)
    try:
        with svc.atomic():
            created = svc.create_monthly_cutoffs(now=now, target_boundary=body.cutoff_at)
            confirmed = svc.finalize_due_cutoffs(now=now, only_at=body.cutoff_at)
            rows, pending = svc.list_cutoffs(status='PENDING',
                from_at=utc(body.cutoff_at), to_at=utc(body.cutoff_at) + timedelta(seconds=1))
    except CutoffError as exc:
        cutoff_error(exc)
    return {'job_id':str(uuid4()), 'cutoff_at':utc(body.cutoff_at).isoformat(),
            'created_count':created, 'confirmed_count':confirmed, 'pending_count':pending}


class ResolveAlertInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    resolution_note: str = Field(min_length=8, max_length=1000)


@alerts_router.post('/meter-alerts/{alert_id}/resolve')
def resolve_meter_alert(alert_id: UUID, body: ResolveAlertInput, db: Db,
                        actor: UUID = Header(alias='X-Auth-User-Id')):
    try:
        row = MeteringService(db).resolve_meter_alert(alert_id, note=body.resolution_note)
    except CutoffError as exc:
        cutoff_error(exc)
    return MeterAlertOut.model_validate(row).model_dump(mode='json')

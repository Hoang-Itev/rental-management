"""Owner-only read endpoints; existing Nginx /api/v1/meters routes require JWT."""
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from datetime import datetime
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

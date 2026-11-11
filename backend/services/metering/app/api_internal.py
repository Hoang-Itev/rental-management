"""Service-token-only diagnostics and the planned Metering listing for Simulator."""
from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import MeteringSettings, get_settings
from app.db import get_db
from app.service import MeteringService

router = APIRouter(prefix="/internal/v1", tags=["Internal Metering"])


def require_service_token(
    candidate: Annotated[str | None, Header(alias="X-Service-Token")] = None,
    settings: MeteringSettings = Depends(get_settings),
) -> None:
    if not candidate or not hmac.compare_digest(candidate, settings.service_token):
        raise HTTPException(status_code=403, detail="Invalid service credential")


def meter_view(row) -> dict:
    return {
        "id": str(row.id), "room_id": str(row.room_id), "meter_code": row.meter_code,
        "meter_type": row.meter_type, "unit": row.unit, "status": row.status,
    }


@router.get("/rooms/{room_id}/meters", dependencies=[Depends(require_service_token)])
def meters_for_room(room_id: UUID, db: Session = Depends(get_db)):
    return {"items": [meter_view(r) for r in MeteringService(db).meters_for_room(room_id)]}


@router.get("/meters", dependencies=[Depends(require_service_token)])
def internal_meters(
    status: str | None = Query(default="ACTIVE", pattern="^(ACTIVE|INACTIVE)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows, total = MeteringService(db).list_meters(status, page, page_size)
    return {"items": [meter_view(r) for r in rows],
            "meta": {"page": page, "page_size": page_size, "total": total}}


@router.get('/meters/{meter_id}/baseline', dependencies=[Depends(require_service_token)])
def meter_baseline(meter_id: UUID, db: Session = Depends(get_db)):
    from app.telemetry import UnknownMeter
    try:
        data = MeteringService(db).meter_baseline(meter_id)
    except UnknownMeter as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'meter_id': str(meter_id), 'reading_value': str(data['reading_value']),
            'measured_at': data['measured_at'].isoformat(), 'source': data['source']}


@router.get('/rooms/{room_id}/cutoffs', dependencies=[Depends(require_service_token)])
def confirmed_cutoffs_for_room(room_id: UUID,
    from_at: str | None = Query(default=None, alias='from'),
    to_at: str | None = Query(default=None, alias='to'),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Billing-only read projection. Only current CONFIRMED versions exposed."""
    from datetime import datetime
    from app.api import cutoff_payload
    from app.cutoffs import CutoffError
    from pydantic import TypeAdapter, AwareDatetime
    adapter = TypeAdapter(AwareDatetime)
    try:
        start = adapter.validate_python(from_at) if from_at is not None else None
        end = adapter.validate_python(to_at) if to_at is not None else None
    except Exception as exc:
        raise HTTPException(status_code=422, detail='from/to must be ISO timezone-aware') from exc
    if start is not None and end is not None and start >= end:
        raise HTTPException(status_code=422, detail='to must be after from')
    rows, count = MeteringService(db).list_cutoffs(
        room_id=room_id, status='CONFIRMED', from_at=start, to_at=end,
        page=page, page_size=page_size)
    return {'items': [cutoff_payload(db, row) for row in rows],
            'meta': {'page': page, 'page_size': page_size, 'total': count}}

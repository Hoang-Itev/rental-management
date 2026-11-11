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


@router.get(
    "/meters/{meter_id}/baseline",
    dependencies=[Depends(require_service_token)]
)
def meter_baseline(
    meter_id: UUID,
    db: Session = Depends(get_db)
):
    from app.telemetry import UnknownMeter

    try:
        data = MeteringService(db).meter_baseline(meter_id)
    except UnknownMeter as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "meter_id": str(meter_id),
        "reading_value": str(data["reading_value"]),
        "measured_at": data["measured_at"].isoformat(),
        "source": data["source"],
    }

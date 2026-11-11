"""Private Tenant/Billing room validation; requires X-Service-Token, not public JWT."""
from __future__ import annotations

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import RoomSettings, get_settings
from app.db import get_db
from app.schemas import RoomValidation
from app.service import RoomService

router = APIRouter(prefix="/internal/v1", tags=["Internal-Room"], include_in_schema=False)


@router.get("/rooms/{room_id}/validation", response_model=RoomValidation)
def validate_room(room_id: UUID,
                  db: Annotated[Session, Depends(get_db)],
                  settings: Annotated[RoomSettings, Depends(get_settings)],
                  x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None):
    if x_service_token is None or not compare_digest(x_service_token, settings.service_token):
        raise HTTPException(status_code=403, detail="internal_only")
    return RoomService(db).validate_room(room_id)

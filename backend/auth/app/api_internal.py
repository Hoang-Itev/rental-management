"""Gateway-only JWT verification endpoint; never published by Nginx."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import security, service
from app.api import unauthorized
from app.config import AuthSettings, get_settings
from app.db import get_db

router = APIRouter(prefix="/internal/v1/auth", tags=["Internal-Auth"], include_in_schema=False)


@router.get("/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> Response:
    if not security.valid_service_token(x_service_token, settings):
        raise HTTPException(status_code=403, detail="forbidden_internal")
    try:
        user = service.current_user(session, authorization, settings)
    except service.AuthenticationRejected as exc:
        raise unauthorized() from exc
    return Response(status_code=204, headers={"X-Auth-User-Id": str(user.id), "Cache-Control": "no-store"})

"""Two public HTTP routes: POST login and GET the authenticated admin profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import AuthSettings, get_settings
from app.db import get_db
from app import service
from app.schemas import LoginRequest, LoginResponse, UserPublic

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(scheme_name="BearerAuth", auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_settings)],
) -> LoginResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.login(session, body.email, body.password, settings)
    except service.AuthenticationRejected as exc:
        raise unauthorized() from exc


@router.get("/me", response_model=UserPublic)
def me(
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> UserPublic:
    response.headers["Cache-Control"] = "no-store"
    try:
        user = service.current_user(session, f"Bearer {credentials.credentials}" if credentials else None, settings)
    except service.AuthenticationRejected as exc:
        raise unauthorized() from exc
    return UserPublic.model_validate(user)

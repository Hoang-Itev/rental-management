"""Login and active-user authorization independent from FastAPI and Nginx."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import AuthSettings
from app.models import User
from app import repository, security
from app.schemas import LoginResponse, UserPublic


class AuthenticationRejected(Exception):
    """Generic authentication failure; do not disclose user existence."""


def login(session: Session, email: str, password: str, settings: AuthSettings) -> LoginResponse:
    """Validate login, update last_login_at and issue a short-lived access JWT."""
    user = repository.get_user_by_email(session, email)
    if user is None:
        security.reject_unknown_user(password)
        raise AuthenticationRejected()
    if not security.verify_password(password, user.password_hash) or not user.is_active:
        raise AuthenticationRejected()
    repository.record_successful_login(session, user, datetime.now(timezone.utc))
    return LoginResponse(
        access_token=security.create_access_token(user.id, settings),
        expires_in=settings.jwt_ttl_seconds,
        user=UserPublic.model_validate(user),
    )


def current_user(session: Session, authorization: str | None, settings: AuthSettings) -> User:
    """Verify signed JWT and check DB-backed is_active on EVERY protected request."""
    try:
        user_id = security.decode_access_token(security.bearer_token(authorization), settings)
    except security.InvalidAccessToken as exc:
        raise AuthenticationRejected() from exc
    user = repository.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AuthenticationRejected()
    return user

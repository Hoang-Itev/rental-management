"""Login authentication and current-user resolution for the Auth service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app import repository as repo, security
from app.config import AuthSettings
from app.schemas import LoginResponse, UserPublic


class AuthenticationRejected(Exception):
    """Credentials, token, or account state rejected; do not leak the reason."""


def login(session: Session, email: str, password: str, settings: AuthSettings) -> LoginResponse:
    """Verify credentials, record last_login_at, and issue a short-lived JWT."""
    user = repo.get_user_by_email(session, email)
    if user is None:
        # Perform comparable Argon2 work to limit email enumeration via timing.
        security.reject_unknown_user(password)
        raise AuthenticationRejected()
    if not security.verify_password(password, user.password_hash):
        raise AuthenticationRejected()
    if not user.is_active:
        raise AuthenticationRejected()

    token = security.create_access_token(user.id, settings)
    repo.record_successful_login(session, user, datetime.now(timezone.utc))
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_ttl_seconds,
        user=UserPublic.model_validate(user),
    )


def current_user(session: Session, authorization: str | None, settings: AuthSettings):
    """Decode a Bearer JWT and re-check the account is still active."""
    try:
        token = security.bearer_token(authorization)
        user_id: UUID = security.decode_access_token(token, settings)
    except security.InvalidAccessToken as exc:
        raise AuthenticationRejected() from exc

    user = repo.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AuthenticationRejected()
    return user
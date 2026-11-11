"""Argon2id password verification and strictly validated HS256 access tokens."""

from datetime import datetime, timedelta, timezone
from secrets import compare_digest
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt

from app.config import AuthSettings


_hasher = PasswordHasher()
# This is deliberately NOT a usable login credential. Its only purpose is to
# perform comparable Argon2 work for nonexistent accounts to limit enumeration.
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "u/+zafF322QErr14eGHL6w$"
    "o+Vn1f74j/O4DGz9cF2p40ZeDC5ACGUjjXnUXWB8dsM"
)


class InvalidAccessToken(Exception):
    """A bearer token is invalid or expired; never expose a decoding reason."""


def hash_password(password: str) -> str:
    """Generate Argon2id hash, compatible with the existing pwdlib demo seed."""
    if not password or len(password) > 1024:
        raise ValueError("password length must be between 1 and 1024")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Fail closed on invalid stored hashes, including unrecognized algorithms."""
    try:
        return bool(_hasher.verify(password_hash, password))
    except (InvalidHashError, VerifyMismatchError, VerificationError, TypeError, ValueError):
        return False


def reject_unknown_user(password: str) -> None:
    """Perform comparable verification work for an email absent from the DB."""
    verify_password(password, _DUMMY_HASH)


def valid_service_token(provided: str | None, settings: AuthSettings) -> bool:
    return bool(provided) and compare_digest(provided, settings.service_token)


def bearer_token(authorization: str | None) -> str:
    """Only accept one well-formed Authorization: Bearer <JWT> header."""
    if not authorization or len(authorization) > 8192:
        raise InvalidAccessToken()
    pieces = authorization.split()
    if len(pieces) != 2 or pieces[0].casefold() != "bearer" or not pieces[1]:
        raise InvalidAccessToken()
    if len(pieces[1]) > 4096:
        raise InvalidAccessToken()
    return pieces[1]


def create_access_token(user_id: UUID, settings: AuthSettings, *, now: datetime | None = None) -> str:
    """Use UUID identity, issuer, audience, unique jti and short expiry."""
    issued = now or datetime.now(timezone.utc)
    if issued.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    issued = issued.astimezone(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued,
        "nbf": issued,
        "exp": issued + timedelta(seconds=settings.jwt_ttl_seconds),
        "jti": str(uuid4()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: AuthSettings) -> UUID:
    """Reject missing claims, wrong algorithm/audience/issuer/type, bad UUID and expiry."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti"]},
            leeway=0,
        )
        if claims.get("typ") != "access":
            raise InvalidAccessToken()
        UUID(str(claims["jti"]))  # Token ID must be a well-formed UUID.
        return UUID(str(claims["sub"]))
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise InvalidAccessToken() from exc

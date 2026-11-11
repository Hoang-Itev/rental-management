"""Auth-local SQLAlchemy queries. Never access other service databases."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def get_user_by_email(session: Session, email: str) -> User | None:
    """Exact case-insensitive match, backed by uq_users_email_ci."""
    statement = select(User).where(func.lower(User.email) == email.strip().lower())
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def record_successful_login(session: Session, user: User, at: datetime) -> None:
    """Commit only on valid credentials; rollback on DB error is caller's concern."""
    user.last_login_at = at
    session.add(user)
    session.commit()

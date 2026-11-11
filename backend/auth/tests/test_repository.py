from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app import repository
from app.models import User


def test_lookup_email_normalized():
    session = MagicMock()
    returned = object()
    session.scalar.return_value = returned
    assert repository.get_user_by_email(session, "  OWNER@EXAMPLE.COM ") is returned
    compiled = str(session.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "lower(users.email)" in compiled.lower()
    assert "owner@example.com" in compiled


def test_lookup_uuid():
    session = MagicMock()
    user_id = uuid4()
    returned = object()
    session.get.return_value = returned
    assert repository.get_user_by_id(session, user_id) is returned
    session.get.assert_called_once_with(User, user_id)


def test_record_login_commits():
    session = MagicMock()
    user = SimpleNamespace(last_login_at=None)
    now = datetime.now(timezone.utc)
    repository.record_successful_login(session, user, now)
    assert user.last_login_at == now
    session.add.assert_called_once_with(user)
    session.commit.assert_called_once()

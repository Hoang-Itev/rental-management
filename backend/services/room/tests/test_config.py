import pytest
from pydantic import ValidationError
from app.config import RoomSettings


def test_valid_secret():
    assert RoomSettings(SERVICE_TOKEN='t'*24).service_token=='t'*24


def test_invalid_secret():
    with pytest.raises(ValidationError):RoomSettings(SERVICE_TOKEN='short')

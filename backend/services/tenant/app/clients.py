"""Internal service-to-service HTTP. Fail closed on timeout, invalid payload, or 403."""
from __future__ import annotations
from uuid import UUID
import httpx
from pydantic import ValidationError
from app.config import TenantSettings
from app.schemas import RoomValidation

class RoomUnavailable(Exception):
    """Room internal validation is unavailable or returned invalid data."""

class RoomClient:
    def __init__(self, settings: TenantSettings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def validate(self, room_id: UUID) -> RoomValidation:
        url = self.settings.room_url.rstrip('/') + f'/internal/v1/rooms/{room_id}/validation'
        try:
            with httpx.Client(timeout=self.settings.room_timeout_seconds,
                              transport=self.transport, trust_env=False) as client:
                response = client.get(url, headers={'X-Service-Token': self.settings.service_token,
                                                    'Accept': 'application/json'})
            response.raise_for_status()
            data = RoomValidation.model_validate(response.json())
            if data.room_id != room_id or (data.exists and not data.room_code):
                raise RoomUnavailable('Room returned mismatched/malformed validation result')
            return data
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise RoomUnavailable('Room internal validation unavailable') from exc

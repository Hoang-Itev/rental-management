"""Room projection of Tenant ContractStarted/ContractEnded events."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.orm import Session
from app import models as m, repository as repo


class FutureEvent(Exception):
    """The business boundary has not occurred yet; delivery must be deferred."""


class ContractData(BaseModel):
    contract_id: UUID
    room_id: UUID


class ContractEnvelope(BaseModel):
    model_config = ConfigDict(extra='ignore')
    event_id: UUID
    event_type: Literal['ContractStarted','ContractEnded']
    event_version: Literal[1]
    occurred_at: datetime
    effective_at: datetime
    correlation_id: UUID
    aggregate_id: UUID
    data: ContractData

    @model_validator(mode='after')
    def validate_event(self):
        if self.aggregate_id != self.data.contract_id:
            raise ValueError('Contract event aggregate_id must equal contract_id')
        if self.effective_at.tzinfo is None:
            raise ValueError('effective_at must be timezone-aware')
        return self


def apply_contract_event(session: Session, raw: dict, *, now: datetime | None = None) -> str:
    event = ContractEnvelope.model_validate(raw)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    if event.effective_at > now:
        raise FutureEvent('Contract event is not due')
    tx = session.begin_nested() if session.in_transaction() else session.begin()
    with tx:
        # Lock room FIRST: serializes all events for the same physical room.
        room = repo.get(session, m.Room, event.data.room_id, lock=True)
        if room is None:
            raise LookupError('Room does not exist for contract projection')
        if session.get(m.ProcessedEvent,event.event_id) is not None:
            return 'duplicate'
        stamped = room.occupancy_updated_at
        instant = event.effective_at.astimezone(timezone.utc)
        if stamped is not None and stamped.tzinfo is None:
            stamped = stamped.replace(tzinfo=timezone.utc)
        status = 'stale'
        if stamped is None or instant >= stamped:
            if event.event_type == 'ContractStarted':
                if room.occupancy_contract_id == event.data.contract_id:
                    status = 'duplicate-contract'
                elif (stamped is None or instant > stamped or room.occupancy_contract_id is None):
                    room.occupancy_contract_id = event.data.contract_id
                    room.occupancy_updated_at = instant
                    status = 'applied'
                else:
                    # Equal timestamp, different active occupant: never overwrite.
                    raise ValueError('Conflicting start at same effective timestamp')
            else:
                if room.occupancy_contract_id == event.data.contract_id:
                    room.occupancy_contract_id = None
                    room.occupancy_updated_at = instant
                    status = 'applied'
                elif room.occupancy_contract_id is None and (stamped is None or instant > stamped):
                    room.occupancy_updated_at = instant
                    status = 'applied-empty'
        repo.add(session, m.ProcessedEvent(event_id=event.event_id,event_type=event.event_type))
        session.flush()
    return status

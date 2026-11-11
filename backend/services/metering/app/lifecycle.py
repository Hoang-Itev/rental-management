"""Independent Contract lifecycle envelope for Metering service."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, model_validator


class FutureEvent(Exception):
    pass


class ContractData(BaseModel):
    contract_id: UUID
    room_id: UUID


class ContractEnvelope(BaseModel):
    model_config=ConfigDict(extra='ignore')
    event_id: UUID
    event_type: Literal['ContractStarted','ContractEnded']
    event_version: Literal[1]
    occurred_at: datetime
    effective_at: datetime
    correlation_id: UUID
    aggregate_id: UUID
    data: ContractData

    @model_validator(mode='after')
    def check(self):
        if self.aggregate_id!=self.data.contract_id:
            raise ValueError('Mismatched contract aggregate_id')
        if self.effective_at.tzinfo is None:
            raise ValueError('effective_at must include timezone')
        return self

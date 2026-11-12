"""P06 telemetry contract. The MQTT body is cumulative, never a delta."""
from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

ReadingValue = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=3)]

class Telemetry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    meter_id: UUID
    measured_at: AwareDatetime
    reading_value: ReadingValue

    @field_validator('measured_at')
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        # Database PK precision is microseconds. Don't silently round measured_at.
        return value.astimezone(timezone.utc)

class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    meter_id: UUID
    measured_at: datetime
    reading_value: Decimal
    received_at: datetime
    validation_status: Literal['VALID','SUSPECT','REJECTED']
    anomaly_reason: str | None

class MeterAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    meter_id: UUID
    alert_type: str
    status: str
    related_measured_at: datetime | None
    detected_at: datetime
    detail: dict

# P07 cutoffs. Monetary calculations belong to Billing, never Metering.
class ManualCutoffInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reading_value: ReadingValue
    manual_reason: str = Field(min_length=8, max_length=1000)


class CutoffReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    contract_id: UUID
    reason_type: Literal['CONTRACT_START', 'CONTRACT_END']


class CutoffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    meter_id: UUID
    contract_id: UUID | None
    cutoff_type: Literal['CONTRACT_START', 'CONTRACT_END', 'MONTHLY']
    cutoff_at: datetime
    reading_value: Decimal | None
    source: Literal['AUTOMATIC', 'MANUAL']
    source_reading_at: datetime | None
    manual_reason: str | None
    status: Literal['PENDING', 'CONFIRMED', 'SUPERSEDED']
    confirmed_at: datetime | None
    confirmed_by: UUID | None
    supersedes_id: UUID | None
    created_at: datetime
    reasons: list[CutoffReasonOut] = Field(default_factory=list)


class JobResult(BaseModel):
    monthly_created: int
    auto_confirmed: int
    offline_alerts_created: int


class MonthlyRunInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cutoff_at: AwareDatetime


class MeterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    room_id: UUID
    meter_code: str
    meter_type: Literal['ELECTRICITY', 'WATER']
    unit: str
    status: Literal['ACTIVE', 'INACTIVE']


class RoomMeterList(BaseModel):
    items: list[MeterOut]


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


T = TypeVar('T')


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class MonthlyRunResult(BaseModel):
    job_id: UUID
    cutoff_at: datetime
    created_count: int
    confirmed_count: int
    pending_count: int


class MeterBaseline(BaseModel):
    meter_id: UUID
    reading_value: str
    measured_at: datetime
    source: str


class UtilityUsage(BaseModel):
    meter_id: UUID
    meter_type: Literal['ELECTRICITY', 'WATER']
    unit: str
    start_cutoff_id: UUID
    end_cutoff_id: UUID
    start_reading: str
    end_reading: str
    consumption: str




class RoomUsage(BaseModel):
    room_id: UUID
    contract_id: UUID
    period_start: date
    period_end_exclusive: date
    status: Literal['PENDING_CUTOFF', 'READY']
    missing_cutoffs: list[str]
    utilities: list[UtilityUsage]

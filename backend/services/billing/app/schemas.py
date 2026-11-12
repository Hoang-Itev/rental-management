"""P08 input/output snapshots for a pure, auditable VND invoice calculator.

All intervals are [period_start, period_end), consistent with Tenant/Billing V3.
The next phase (P09) collects and validates cross-service data before calling P08.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VND = Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]
MeterValue = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=3)]
MeterType = Literal["ELECTRICITY", "WATER"]
LineType = Literal["RENT", "ELECTRICITY", "WATER", "SERVICE"]


class StrictSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TermSnapshot(StrictSnapshot):
    """Tenant contract_terms snapshot; effective_to is exclusive (None=open)."""

    id: UUID
    effective_from: date
    effective_to: date | None = None
    monthly_rent: VND
    electricity_unit_price: VND
    water_unit_price: VND
    monthly_service_fee: VND = 0

    @model_validator(mode="after")
    def valid_dates(self):
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("term effective_to must be after effective_from")
        return self


class UsageSnapshot(StrictSnapshot):
    """One metering interval bounded by *confirmed* cutoff snapshots.

    A term-price boundary must have its own usage segment and confirmed cutoff;
    P08 intentionally does not estimate consumption from elapsed days.
    """

    meter_type: MeterType
    meter_id: UUID
    period_start: date
    period_end: date
    source_cutoff_start_id: UUID
    source_cutoff_end_id: UUID
    start_cutoff_status: Literal["CONFIRMED"]
    end_cutoff_status: Literal["CONFIRMED"]
    start_reading: MeterValue
    end_reading: MeterValue

    @field_validator("start_reading", "end_reading", mode="before")
    @classmethod
    def reject_floating_point(cls, value):
        # JSON decimal strings and Decimal are safe; binary floats are not.
        if isinstance(value, float) or isinstance(value, bool):
            raise ValueError("meter readings must be decimal strings or Decimal, never float")
        return value

    @model_validator(mode="after")
    def valid_interval(self):
        if self.period_end <= self.period_start:
            raise ValueError("usage period_end must be after period_start")
        if self.end_reading < self.start_reading:
            raise ValueError("meter cumulative reading decreased")
        return self


class InvoiceCalculationInput(StrictSnapshot):
    """A single contract's already-clipped invoice period and immutable inputs."""

    period_start: date
    period_end: date
    terms: list[TermSnapshot] = Field(min_length=1)
    usage_segments: list[UsageSnapshot] = Field(min_length=2)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_end <= self.period_start:
            raise ValueError("invoice period_end must be after period_start")
        return self


class CalculatedLine(StrictSnapshot):
    """Fields map to invoice_items; daily unit_price is display-only (4dp)."""

    item_type: LineType
    description: str
    quantity: Decimal
    unit: Literal["DAY", "KWH", "M3"]
    unit_price: Decimal
    amount: VND
    period_start: date
    period_end: date
    meter_start_value: Decimal | None = None
    meter_end_value: Decimal | None = None
    source_term_id: UUID
    source_cutoff_start_id: UUID | None = None
    source_cutoff_end_id: UUID | None = None


class InvoiceCalculationResult(StrictSnapshot):
    period_start: date
    period_end: date
    items: list[CalculatedLine]
    total_amount: VND

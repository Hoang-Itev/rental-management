"""P08 input/output snapshots for a pure, auditable VND invoice calculator.

All intervals are [period_start, period_end), consistent with Tenant/Billing V3.
The next phase (P09) collects and validates cross-service data before calling P08.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


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


class BillingRunRequest(StrictSnapshot):
    billing_month: date

    @field_validator("billing_month")
    @classmethod
    def first_of_month(cls, value):
        if value.day != 1:
            raise ValueError("billing_month must be the first of the month")
        return value


class BillingContext(BaseModel):
    contract_id: UUID
    room_id: UUID
    contract_status: str
    tenant_name: str
    tenant_email: str | None = None
    room_code: str
    chargeable_from: date
    chargeable_to_exclusive: date
    terms: list[TermSnapshot]


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class InvoiceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_code: str
    contract_id: UUID
    room_id: UUID
    invoice_type: Literal["PERIODIC", "FINAL"]
    billing_month: date | None
    period_start: date
    period_end: date
    status: Literal["DRAFT", "ISSUED", "PAID", "VOID"]
    blocked_reason: str | None
    revision: int
    replaces_invoice_id: UUID | None
    void_reason: str | None
    voided_at: datetime | None
    total_amount: int
    due_date: date
    issued_at: datetime | None
    paid_at: datetime | None
    tenant_name_snapshot: str
    tenant_email_snapshot: str | None
    room_code_snapshot: str


class InvoiceItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    item_type: LineType
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: VND
    period_start: date | None
    period_end: date | None
    meter_start_value: Decimal | None
    meter_end_value: Decimal | None
    source_term_id: UUID | None
    source_cutoff_start_id: UUID | None
    source_cutoff_end_id: UUID | None

    @field_serializer("quantity", "unit_price", "meter_start_value", "meter_end_value")
    def serialize_decimal(self, value: Decimal | None):
        return float(value) if value is not None else None


class InvoiceDetail(InvoiceView):
    items: list[InvoiceItemView]


class InvoiceList(BaseModel):
    items: list[InvoiceView]
    meta: PageMeta


class BillingRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    billing_month: date
    trigger_type: Literal["MANUAL", "SCHEDULED"]
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    started_at: datetime
    finished_at: datetime | None
    issued_count: int
    waiting_count: int
    skipped_count: int
    failed_count: int


class BillingRunList(BaseModel):
    items: list[BillingRunView]
    meta: PageMeta


class AccessLinkRequest(StrictSnapshot):
    source_event_id: UUID
    recipient_email: str = Field(min_length=3, max_length=254)


class AccessLink(BaseModel):
    url: str
    expires_at: datetime


class PublicInvoiceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_type: LineType
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: int

    @field_serializer("quantity", "unit_price")
    def serialize_decimal(self, value: Decimal):
        return float(value)


class PublicInvoiceView(BaseModel):
    invoice_code: str
    room_code: str
    tenant_name: str
    period_start: date
    period_end: date
    status: Literal["ISSUED", "PAID"]
    total_amount: int
    due_date: date
    items: list[PublicInvoiceItem]


class MomoPaymentSession(BaseModel):
    payment_attempt_id: UUID
    status: Literal["PENDING", "SUCCESS"]
    reused_pending_attempt: bool
    pay_url: str | None = None
    expires_at: datetime | None = None


class MomoResult(BaseModel):
    model_config = ConfigDict(strict=True)

    partnerCode: str
    orderId: str
    requestId: str
    resultCode: int
    amount: int | None = None
    transId: int | None = None
    payUrl: str | None = None


class MomoIPN(StrictSnapshot):
    model_config = ConfigDict(extra="ignore", strict=True)

    partnerCode: str = Field(max_length=50)
    orderId: str = Field(min_length=1, max_length=120)
    requestId: str = Field(min_length=1, max_length=120)
    amount: int = Field(ge=0, le=9223372036854775807)
    resultCode: int
    transId: int
    message: str = Field(max_length=2048)
    orderInfo: str = Field(max_length=1024)
    orderType: str = Field(max_length=100)
    payType: str = Field(max_length=100)
    responseTime: int
    extraData: str = Field(max_length=4096)
    signature: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class ReconcilePayments(StrictSnapshot):
    payment_attempt_id: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


class PaymentAttemptView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    provider: str
    order_id: str
    request_id: str
    provider_transaction_id: str | None
    amount: int
    status: str
    pay_url: str | None
    expires_at: datetime | None
    result_code: str | None
    confirmed_at: datetime | None


class PaymentAttemptList(BaseModel):
    items: list[PaymentAttemptView]
    meta: PageMeta


class FinalInvoiceRequest(StrictSnapshot):
    contract_id: UUID


class InvoiceReason(StrictSnapshot):
    reason: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value.strip()


class AdjustmentCreate(InvoiceReason):
    amount_delta: Annotated[int, Field(strict=True, ge=-9223372036854775808, le=9223372036854775807)]

    @field_validator("amount_delta")
    @classmethod
    def nonzero_delta(cls, value):
        if value == 0:
            raise ValueError("amount_delta must not be zero")
        return value


class ResolveAdjustment(StrictSnapshot):
    status: Literal["RESOLVED", "REJECTED"]
    resolution_note: str = Field(min_length=1, max_length=2000)

    @field_validator("resolution_note")
    @classmethod
    def nonblank_note(cls, value):
        if not value.strip():
            raise ValueError("resolution_note must not be blank")
        return value.strip()


class AdjustmentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    reason: str
    amount_delta: int
    status: Literal["OPEN", "RESOLVED", "REJECTED"]
    resolution_note: str | None
    created_by: UUID | None
    created_at: datetime
    resolved_at: datetime | None


class AdjustmentList(BaseModel):
    items: list[AdjustmentView]
    meta: PageMeta

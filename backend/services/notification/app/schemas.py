from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvoiceIssuedData(BaseModel):
    invoice_id: UUID
    invoice_code: str = Field(min_length=1, max_length=80, pattern=r"^[^\r\n]+$")
    recipient_email: str = Field(max_length=254, pattern=r"^[^\s@<>,;]+@[^\s@<>,;]+$")
    tenant_name: str
    room_code: str
    total_amount: int = Field(ge=0)
    period_start: date
    period_end_exclusive: date
    due_date: date


class InvoiceIssued(BaseModel):
    event_id: UUID
    event_type: Literal["InvoiceIssued"]
    event_version: Literal[1]
    occurred_at: datetime
    correlation_id: UUID
    aggregate_id: UUID
    data: InvoiceIssuedData

    @model_validator(mode="after")
    def validate_scope(self):
        if self.aggregate_id != self.data.invoice_id or self.data.period_end_exclusive <= self.data.period_start:
            raise ValueError("Invalid invoice scope")
        return self


class EmailJobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_event_id: UUID
    email_type: str
    invoice_id: UUID | None
    recipient_email: str
    subject: str
    status: str
    attempt_count: int
    next_attempt_at: datetime | None
    sent_at: datetime | None
    last_error: str | None


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class EmailJobPage(BaseModel):
    items: list[EmailJobView]
    meta: PageMeta

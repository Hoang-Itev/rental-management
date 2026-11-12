"""P04 Tenant API: strict payloads and [from, to) contract term versions."""
from __future__ import annotations
from datetime import date, datetime
import re
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True,min_length=1,max_length=200)]
Code = Annotated[str, StringConstraints(strip_whitespace=True,min_length=1,max_length=60,pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')]
Phone = Annotated[str, StringConstraints(strip_whitespace=True,min_length=5,max_length=30)]
Money = Annotated[int, Field(ge=0,le=9223372036854775807)]
Status = Literal['DRAFT','SCHEDULED','ACTIVE','EXPIRED_PENDING','ENDED','CANCELLED']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Patch(Strict):
    @model_validator(mode='after')
    def non_empty(self):
        if not self.model_fields_set:
            raise ValueError('PATCH requires at least one field')
        return self

class TenantCreate(Strict):
    full_name: Name
    phone: Phone | None = None
    email: Annotated[str, StringConstraints(strip_whitespace=True,max_length=254)] | None = None
    note: Annotated[str, StringConstraints(max_length=5000)] | None = None
    @model_validator(mode='after')
    def valid_email(self):
        if self.email is not None and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', self.email):
            raise ValueError('invalid email')
        return self

class TenantPatch(Patch):
    full_name: Name | None = None
    phone: Phone | None = None
    email: Annotated[str, StringConstraints(strip_whitespace=True,max_length=254)] | None = None
    note: Annotated[str, StringConstraints(max_length=5000)] | None = None
    @model_validator(mode='after')
    def valid_patch(self):
        if 'full_name' in self.model_fields_set and self.full_name is None:
            raise ValueError('full_name must not be null')
        if self.email is not None and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', self.email):
            raise ValueError('invalid email')
        return self

class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str
    phone: str | None
    email: str | None
    note: str | None

class TermInput(Strict):
    effective_from: date
    effective_to: date | None = None  # EXCLUSIVE; NULL = unbounded
    monthly_rent: Money
    electricity_unit_price: Money
    water_unit_price: Money
    monthly_service_fee: Money = 0
    @model_validator(mode='after')
    def valid_dates(self):
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError('effective_to must follow effective_from (exclusive)')
        return self

class TermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    contract_id: UUID
    effective_from: date
    effective_to: date | None
    monthly_rent: int
    electricity_unit_price: int
    water_unit_price: int
    monthly_service_fee: int

class ContractCreate(Strict):
    contract_code: Code
    room_id: UUID
    representative_tenant_id: UUID
    start_date: date
    end_date: date  # INCLUSIVE
    initial_terms: TermInput
    deposit_amount: Money | None = None
    @model_validator(mode='after')
    def date_order(self):
        if self.end_date < self.start_date or self.end_date == date.max:
            raise ValueError('invalid contract date interval')
        if self.initial_terms.effective_from != self.start_date:
            raise ValueError('initial_terms.effective_from must equal start_date')
        if self.initial_terms.effective_to is not None and self.initial_terms.effective_to > date.fromordinal(self.end_date.toordinal()+1):
            raise ValueError('term exceeds contract end')
        return self

class ContractPatch(Patch):
    contract_code: Code | None = None
    representative_tenant_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    deposit_amount: Money | None = None
    @model_validator(mode='after')
    def required_fields(self):
        if any(getattr(self,field) is None for field in self.model_fields_set if field != 'deposit_amount'):
            raise ValueError('contract fields cannot be null')
        return self

class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    contract_code: str
    room_id: UUID
    room_code_snapshot: str
    representative_tenant_id: UUID
    start_date: date
    end_date: date
    actual_end_date: date | None
    status: Status
    deposit_amount: int | None
    end_reason: str | None

class ContractEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    contract_id: UUID
    event_type: str
    occurred_at: datetime
    actor_id: UUID | None
    reason: str | None
    details: dict

T = TypeVar('T')
class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta

class RoomValidation(BaseModel):
    room_id: UUID
    exists: bool
    operational: bool
    property_id: UUID | None = None
    room_code: str | None = None
    occupancy_contract_id: UUID | None = None


class RenewRequest(Strict):
    new_end_date: date
    reason: str | None = Field(default=None, max_length=2000)
    new_terms: TermInput | None = None

class EndRequest(Strict):
    actual_end_date: date
    reason: Name

class LifecycleRun(Strict):
    as_of: datetime | None = None

class LifecycleResult(Strict):
    job_id: UUID
    processed: int
    started: int
    pending_end: int


class CancelRequest(Strict):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class BillableContract(BaseModel):
    contract_id: UUID
    room_id: UUID
    status: Status
    start_date: date
    end_date: date
    actual_end_date: date | None


class BillableContracts(BaseModel):
    items: list[BillableContract]
    next_cursor: UUID | None = None


class PayerOut(BaseModel):
    id: UUID
    full_name: str
    email: str | None


class InternalContract(BaseModel):
    contract: ContractOut
    terms: list[TermOut]
    payer: PayerOut


class BillingTerm(BaseModel):
    id: UUID
    effective_from: date
    effective_to: date | None
    monthly_rent: int
    electricity_unit_price: int
    water_unit_price: int
    monthly_service_fee: int


class BillingContext(BaseModel):
    contract_id: UUID
    room_id: UUID
    contract_status: Status
    tenant_name: str
    tenant_email: str | None
    room_code: str
    chargeable_from: date
    chargeable_to_exclusive: date
    terms: list[BillingTerm]


class ExpiryEligibility(BaseModel):
    contract_id: UUID
    end_date: date
    eligible: bool

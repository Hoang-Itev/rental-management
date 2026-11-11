"""Public Room DTOs. Parent IDs and occupancy data are never client-writeable."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from typing import Annotated

Status = Literal["ACTIVE", "INACTIVE"]
Occupancy = Literal["VACANT", "OCCUPIED", "INACTIVE"]

Name200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Name120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Code60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Area = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]
Rent = Annotated[int, Field(ge=0, le=9223372036854775807)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatchModel(StrictModel):
    @model_validator(mode="after")
    def require_some_field(self):
        if not self.model_fields_set:
            raise ValueError("PATCH request must have at least one field")
        return self


class PropertyCreate(StrictModel):
    name: Name200
    address: Address
    description: str | None = Field(default=None, max_length=5000)


class PropertyPatch(PatchModel):
    name: Name200 | None = None
    address: Address | None = None
    description: str | None = Field(default=None, max_length=5000)
    status: Status | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for field in ("name", "address", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class BuildingCreate(StrictModel):
    name: Name120


class BuildingPatch(PatchModel):
    name: Name120 | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        if any(getattr(self, x) is None for x in self.model_fields_set):
            raise ValueError("building fields cannot be null")
        return self


class FloorCreate(StrictModel):
    floor_number: int = Field(ge=-5, le=200)
    name: Name120 | None = None


class FloorPatch(PatchModel):
    name: Name120 | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class RoomCreateItem(StrictModel):
    room_code: Code60
    area_m2: Area
    listed_rent: Rent
    property_id: UUID | None = None  # Optional sanity check; actual parent is derived from floor.

    @field_validator("room_code")
    @classmethod
    def canonical_code(cls, code: str) -> str:
        return code.upper()


class RoomBulkCreate(StrictModel):
    rooms: list[RoomCreateItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def codes_unique_in_request(self):
        codes = [r.room_code for r in self.rooms]
        if len(codes) != len(set(codes)):
            raise ValueError("duplicate room_code in request")
        return self


class RoomPatch(PatchModel):
    room_code: Code60 | None = None
    area_m2: Area | None = None
    listed_rent: Rent | None = None
    status: Status | None = None

    @field_validator("room_code")
    @classmethod
    def canonical_code(cls, code: str | None) -> str | None:
        return code.upper() if code is not None else None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        if any(getattr(self, x) is None for x in self.model_fields_set):
            raise ValueError("room fields cannot be null")
        return self


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    address: str
    description: str | None
    status: Status


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    property_id: UUID
    name: str
    status: Status


class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    building_id: UUID
    floor_number: int
    name: str | None
    status: Status


class RoomOut(BaseModel):
    id: UUID
    property_id: UUID
    floor_id: UUID
    room_code: str
    area_m2: float
    listed_rent: int
    status: Status
    occupancy_contract_id: UUID | None
    display_occupancy: Occupancy
    occupancy_updated_at: datetime | None

    @classmethod
    def from_room(cls, row):
        occupancy = "INACTIVE" if row.status == "INACTIVE" else ("OCCUPIED" if row.occupancy_contract_id else "VACANT")
        return cls(id=row.id, property_id=row.property_id, floor_id=row.floor_id,
                   room_code=row.room_code, area_m2=float(row.area_m2),
                   listed_rent=row.listed_rent, status=row.status,
                   occupancy_contract_id=row.occupancy_contract_id,
                   display_occupancy=occupancy, occupancy_updated_at=row.occupancy_updated_at)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class RoomValidation(BaseModel):
    room_id: UUID
    exists: bool
    operational: bool
    property_id: UUID | None = None
    room_code: str | None = None


class ErrorOut(BaseModel):
    code: str
    message: str
    correlation_id: UUID

"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/customers.yaml."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

CustomerType = Literal["individual", "company"]

Phone = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{7,14}$")]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]
TaxId = Annotated[str, StringConstraints(max_length=20)]
Notes = Annotated[str, StringConstraints(max_length=2000)]
Discount = Annotated[float, Field(ge=0, le=100)]


class CustomerCreate(BaseModel):
    type: CustomerType
    name: Name
    phone: Phone
    email: EmailStr | None = None
    tax_id: TaxId | None = None
    notes: Notes | None = None
    discount_percent: Discount = 0


class CustomerUpdate(BaseModel):
    """Часткове оновлення: передаються тільки поля, що змінюються."""

    model_config = ConfigDict(extra="forbid")

    type: CustomerType | None = None
    name: Name | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    tax_id: TaxId | None = None
    notes: Notes | None = None
    discount_percent: Discount | None = None


class Customer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: CustomerType
    name: str
    phone: str
    email: str | None
    tax_id: str | None
    notes: str | None
    discount_percent: float
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CustomerPage(BaseModel):
    items: list[Customer]
    total: int
    limit: int
    offset: int


class Error(BaseModel):
    detail: str

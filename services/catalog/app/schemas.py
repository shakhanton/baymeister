"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/catalog.yaml."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.money import Hours, Money

Unit = Literal["pcs", "l", "kg", "m", "set"]
PriceSource = Literal["fixed", "norm_hours", "unknown"]

_SPACES = re.compile(r"\s+")


def _normalize_code(value: str) -> str:
    """Код і артикул — без пробілів і у верхньому регістрі: «oc 90» і «OC90» — одне."""
    return _SPACES.sub("", value).upper()


Code = Annotated[
    str, StringConstraints(min_length=1, max_length=20), AfterValidator(_normalize_code)
]
Sku = Annotated[
    str, StringConstraints(min_length=1, max_length=40), AfterValidator(_normalize_code)
]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]
# Бренд — у верхньому регістрі, як у каталогах: «Mahle» і «MAHLE» — один виробник.
Brand = Annotated[Label, AfterValidator(str.upper)]


# ── Ставка ──────────────────────────────────────────────────────────────────


class LaborRateCreate(BaseModel):
    amount: Money
    effective_from: datetime | None = None


class LaborRate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Money
    effective_from: datetime
    created_at: datetime


# ── Роботи ──────────────────────────────────────────────────────────────────


class ServiceCreate(BaseModel):
    code: Code
    name: Name
    category: Label
    norm_hours: Hours
    fixed_price: Money | None = None


class ServiceUpdate(BaseModel):
    """Часткове оновлення: передаються тільки поля, що змінюються."""

    model_config = ConfigDict(extra="forbid")

    code: Code | None = None
    name: Name | None = None
    category: Label | None = None
    norm_hours: Hours | None = None
    fixed_price: Money | None = None


class Service(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    norm_hours: Hours
    fixed_price: Money | None
    price: Money | None
    price_source: PriceSource
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ServicePage(BaseModel):
    items: list[Service]
    total: int
    limit: int
    offset: int
    labor_rate: Money | None


# ── Запчастини ──────────────────────────────────────────────────────────────


class PartCreate(BaseModel):
    sku: Sku
    brand: Brand
    name: Name
    unit: Unit
    price: Money


class PartUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: Sku | None = None
    brand: Brand | None = None
    name: Name | None = None
    unit: Unit | None = None
    price: Money | None = None


class Part(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    brand: str
    name: str
    unit: Unit
    price: Money
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PartPage(BaseModel):
    items: list[Part]
    total: int
    limit: int
    offset: int


class Error(BaseModel):
    detail: str

"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/work-orders.yaml."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
)

from app.money import Money, Qty, format_2

Status = Literal["open", "in_progress", "done", "closed", "cancelled"]
Kind = Literal["service", "part"]

Text = Annotated[str, StringConstraints(max_length=2000)]
Km = Annotated[int, Field(ge=0, le=9_999_999)]
# Знижка клієнта — рядком, як і гроші: «5.00».
Percent = Annotated[
    Decimal,
    PlainSerializer(format_2, return_type=str),
    WithJsonSchema({"type": "string", "examples": ["5.00"]}),
]


class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    complaint: Text | None = None
    mileage_km: Km | None = None


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complaint: Text | None = None
    mileage_km: Km | None = None
    notes: Text | None = None


class StatusChange(BaseModel):
    status: Status


class LineCreate(BaseModel):
    kind: Kind
    catalog_id: uuid.UUID
    qty: Qty = Decimal("1.000")


class LineUpdate(BaseModel):
    qty: Qty


class Line(BaseModel):
    id: uuid.UUID
    kind: Kind
    catalog_id: uuid.UUID
    code: str
    name: str
    qty: Qty
    unit: str
    unit_price: Money
    amount: Money


class Totals(BaseModel):
    services: Money
    parts: Money
    subtotal: Money
    discount_percent: Percent
    discount: Money
    total: Money


class OrderSummary(BaseModel):
    id: uuid.UUID
    number: str
    status: Status
    customer_id: uuid.UUID
    customer_name: str
    customer_phone: str
    vehicle_id: uuid.UUID
    vehicle_label: str
    total: Money
    opened_at: datetime
    updated_at: datetime


class Order(OrderSummary):
    appointment_id: uuid.UUID | None
    complaint: str | None
    mileage_km: int | None
    notes: str | None
    lines: list[Line]
    totals: Totals
    done_at: datetime | None
    closed_at: datetime | None


class OrderPage(BaseModel):
    items: list[OrderSummary]
    total: int
    limit: int
    offset: int


class Error(BaseModel):
    detail: str

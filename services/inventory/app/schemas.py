"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/inventory.yaml."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.money import Money, Qty

Note = Annotated[str, StringConstraints(max_length=200)]
Location = Annotated[str, StringConstraints(max_length=20, strip_whitespace=True)]


class ReceiptCreate(BaseModel):
    part_id: uuid.UUID
    qty: Qty
    unit_cost: Money
    note: Note | None = None


class CountCreate(BaseModel):
    counted: Qty
    note: Note | None = None


class StockItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: Location | None = None
    min_qty: Qty | None = None


class StockItem(BaseModel):
    part_id: uuid.UUID
    sku: str
    brand: str
    name: str
    unit: str
    location: str | None
    on_hand: Qty
    reserved: Qty
    free: Qty
    min_qty: Qty
    value: Money
    low: bool


class Lot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    received_at: datetime
    qty_received: Qty
    qty_left: Qty
    unit_cost: Money
    source: Literal["receipt", "count"]
    note: str | None


class Reservation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_id: uuid.UUID
    order_id: uuid.UUID
    order_number: str | None
    qty: Qty


class Movement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["receipt", "issue", "count_plus", "count_minus"]
    qty: Qty
    cost: Money
    order_number: str | None
    note: str | None
    created_at: datetime


class StockDetail(StockItem):
    lots: list[Lot]
    reservations: list[Reservation]
    movements: list[Movement]


class StockPage(BaseModel):
    items: list[StockItem]
    total: int
    limit: int
    offset: int


class Error(BaseModel):
    detail: str

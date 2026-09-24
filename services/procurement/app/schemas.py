"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/procurement.yaml."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.money import Money, Qty

Status = Literal["draft", "ordered", "received", "cancelled"]

Name = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Edrpou = Annotated[str, StringConstraints(pattern=r"^\d{8}$|^\d{10}$")]
Phone = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{7,14}$")]
Short = Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]
Note = Annotated[str, StringConstraints(max_length=500)]
Invoice = Annotated[str, StringConstraints(max_length=40, strip_whitespace=True)]


class Error(BaseModel):
    detail: str


# ── Постачальники ──────────────────────────────────────────────────────────


class SupplierCreate(BaseModel):
    name: Name
    edrpou: Edrpou | None = None
    contact: Short | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    note: Note | None = None


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    edrpou: Edrpou | None = None
    contact: Short | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    note: Note | None = None
    active: bool | None = None


class Supplier(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    edrpou: str | None
    contact: str | None
    phone: str | None
    email: str | None
    note: str | None
    active: bool


class SupplierPage(BaseModel):
    items: list[Supplier]
    total: int


# ── Замовлення ─────────────────────────────────────────────────────────────


class OrderCreate(BaseModel):
    supplier_id: uuid.UUID
    note: Note | None = None
    expected_on: date | None = None


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = None
    note: Note | None = None
    expected_on: date | None = None


class StatusChange(BaseModel):
    status: Literal["ordered", "received", "cancelled"]


class LineCreate(BaseModel):
    part_id: uuid.UUID
    qty: Qty
    unit_cost: Money


class LineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qty: Qty | None = None
    unit_cost: Money | None = None


class Line(BaseModel):
    id: uuid.UUID
    part_id: uuid.UUID
    sku: str
    brand: str
    name: str
    unit: str
    qty: Qty
    unit_cost: Money
    amount: Money
    qty_received: Qty


class ReceiptLineCreate(BaseModel):
    line_id: uuid.UUID
    qty: Qty
    # Не вказано — ціна з рядка замовлення.
    unit_cost: Money | None = None


class ReceiptCreate(BaseModel):
    invoice_number: Invoice | None = None
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class Receipt(BaseModel):
    id: uuid.UUID
    invoice_number: str | None
    received_at: datetime
    lines: int
    total: Money


class SupplierRef(BaseModel):
    id: uuid.UUID
    name: str


class Order(BaseModel):
    id: uuid.UUID
    number: str
    status: Status
    auto: bool
    supplier: SupplierRef
    note: str | None
    expected_on: date | None
    created_at: datetime
    ordered_at: datetime | None
    closed_at: datetime | None
    lines: list[Line]
    receipts: list[Receipt]
    total: Money


class OrderSummary(BaseModel):
    id: uuid.UUID
    number: str
    status: Status
    auto: bool
    supplier: SupplierRef
    expected_on: date | None
    created_at: datetime
    lines: int
    total: Money
    # Частка отриманого: 0 — нічого, 1 — усе.
    received_share: float


class OrderPage(BaseModel):
    items: list[OrderSummary]
    total: int


# ── Потреби ────────────────────────────────────────────────────────────────


class OrderRef(BaseModel):
    id: uuid.UUID
    number: str
    status: Status
    supplier: SupplierRef


class Need(BaseModel):
    part_id: uuid.UUID
    sku: str
    brand: str
    name: str
    unit: str
    free: Qty
    min_qty: Qty
    raised_at: datetime
    # Відкрите замовлення, де ця деталь уже є.
    order: OrderRef | None
    # У кого купували востаннє — туди потреба піде сама.
    last_supplier: SupplierRef | None


class NeedOrder(BaseModel):
    supplier_id: uuid.UUID

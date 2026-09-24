import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base

STATUSES = ("draft", "ordered", "received", "cancelled")


class UtcDateTime(TypeDecorator[datetime]):
    """Час завжди з поясом і в UTC — і на Postgres, і на SQLite у тестах."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Час без часового поясу не зберігається")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        result: datetime = value
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


class Supplier(Base):
    """Постачальник. Не видаляється — лише архівується: на нього посилаються замовлення."""

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # name.casefold(): унікальність без огляду на регістр — і кирилиці теж, чого
    # lower() у SQLite не вміє.
    name_key: Mapped[str] = mapped_column(String(120), nullable=False)
    edrpou: Mapped[str | None] = mapped_column(String(10))
    contact: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("name_key", name="uq_suppliers_name_key"),)


class Order(Base):
    """
    Замовлення постачальнику.

    draft → ordered → received; draft і ordered (поки нічого не прийшло) можна
    скасувати. Рядки змінюються тільки в чернетці: відправлене замовлення — це
    вже домовленість з постачальником.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("suppliers.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    # Чернетку склав сам сервіс за сигналом stock.low.
    auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(String(500))
    expected_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    ordered_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    lines: Mapped[list["Line"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Line.created_at",
        lazy="selectin",
    )
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Receipt.received_at",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('draft', 'ordered', 'received', 'cancelled')", name="ck_orders_status"
        ),
        Index("ix_orders_supplier_status", "supplier_id", "status"),
        Index("ix_orders_created", "created_at"),
    )


class Line(Base):
    """Рядок замовлення. Назва, артикул і одиниця — знімок з catalog на момент додавання."""

    __tablename__ = "order_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sku: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(11, 2), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    order: Mapped[Order] = relationship(back_populates="lines")

    __table_args__ = (
        # Одна деталь — один рядок: більше треба — більша кількість.
        UniqueConstraint("order_id", "part_id", name="uq_order_lines_part"),
        CheckConstraint("qty > 0", name="ck_order_lines_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_order_lines_cost"),
        CheckConstraint("qty_received >= 0", name="ck_order_lines_received"),
        Index("ix_order_lines_part", "part_id"),
    )


class Receipt(Base):
    """Прихід за накладною. Одне замовлення може приходити частинами."""

    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    invoice_number: Mapped[str | None] = mapped_column(String(40))
    received_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    received_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    order: Mapped[Order] = relationship(back_populates="receipts")
    lines: Mapped[list["ReceiptLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ReceiptLine(Base):
    """
    Рядок приходу. Його id іде в подію purchase.received — склад за ним
    розпізнає повтор і не заведе ту саму партію двічі.
    """

    __tablename__ = "receipt_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("order_lines.id", ondelete="CASCADE"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(11, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_receipt_lines_qty"),
        CheckConstraint("unit_cost >= 0", name="ck_receipt_lines_cost"),
    )


class Need(Base):
    """
    Потреба: склад сказав, що деталі менше за мінімум (stock.low).

    Закривається, коли прихід підняв залишок вище мінімуму (stock.received
    з low=false), або вручну — «не замовляти». synced_at — час останньої
    застосованої події складу; старіші ігноруються.
    """

    __tablename__ = "needs"

    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    free: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    min_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raised_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


class Counter(Base):
    """
    Лічильник номерів замовлень на рік: PO-2026-00001, PO-2026-00002…

    Номер видається одним UPDATE … RETURNING — рядок блокується до кінця
    транзакції, тож два одночасні замовлення не отримають однаковий номер.
    """

    __tablename__ = "order_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

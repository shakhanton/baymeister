import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base


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


# Статуси, в яких наряд ще можна редагувати: рядки, скаргу, пробіг.
EDITABLE_STATUSES = ("open", "in_progress")


class Counter(Base):
    """
    Лічильник номерів нарядів на рік: 2026-00001, 2026-00002…

    Номер видається одним UPDATE … RETURNING — рядок блокується до кінця
    транзакції, тож два одночасні наряди не отримають однаковий номер.
    """

    __tablename__ = "order_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")

    # Клієнт і авто живуть у своїх блоках. Тут — посилання й копії для списків.
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_synced_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    vehicle_label: Mapped[str] = mapped_column(String(160), nullable=False)
    vehicle_synced_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    # Знижка клієнта на момент відкриття — не змінюється, навіть якщо в
    # customers її змінять: клієнту вже назвали ціну.
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    appointment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    complaint: Mapped[str | None] = mapped_column(String(2000))
    mileage_km: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(2000))

    opened_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["Line"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Line.position",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('open', 'in_progress', 'done', 'closed', 'cancelled')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            "discount_percent >= 0 and discount_percent <= 100", name="ck_orders_discount"
        ),
        CheckConstraint("mileage_km is null or mileage_km >= 0", name="ck_orders_mileage"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_vehicle_id", "vehicle_id"),
        Index("ix_orders_opened_at", "opened_at"),
    )


class Line(Base):
    """Робота або запчастина в наряді — з ціною на момент додавання."""

    __tablename__ = "order_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    catalog_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    code: Mapped[str] = mapped_column(String(110), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(9, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(11, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint("kind in ('service', 'part')", name="ck_order_lines_kind"),
        CheckConstraint("qty > 0", name="ck_order_lines_qty"),
        CheckConstraint("unit_price >= 0", name="ck_order_lines_price"),
        Index("ix_order_lines_order_id", "order_id", "position"),
    )

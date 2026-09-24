import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
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


class Item(Base):
    """
    Картка деталі на складі. Ідентифікатор — той самий, що в catalog.

    Залишку тут немає свідомо: «на складі» — це сума партій, «в резерві» —
    сума активних резервів. Лічильник, який оновлюють окремо, рано чи пізно
    розійдеться з партіями; сума — ні.
    """

    __tablename__ = "items"

    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    # Копія з catalog, оновлюється подіями part.created / part.updated.
    sku: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    catalog_synced_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    location: Mapped[str | None] = mapped_column(String(20))
    min_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (CheckConstraint("min_qty >= 0", name="ck_items_min_qty"),)


class Lot(Base):
    """Партія: прихід зі своєю ціною. Списання бере з найстаріших — FIFO."""

    __tablename__ = "lots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("items.part_id"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    qty_left: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(11, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint("qty_received > 0", name="ck_lots_received"),
        CheckConstraint("qty_left >= 0 and qty_left <= qty_received", name="ck_lots_left"),
        CheckConstraint("unit_cost >= 0", name="ck_lots_cost"),
        CheckConstraint("source in ('receipt', 'count')", name="ck_lots_source"),
        # Лише партії з залишком, у порядку списання.
        Index(
            "ix_lots_fifo",
            "part_id",
            "received_at",
            postgresql_where=text("qty_left > 0"),
            sqlite_where=text("qty_left > 0"),
        ),
    )


class Reservation(Base):
    """
    Резерв під рядок наряду. Один рядок — один резерв, ключ — line_id.

    Рядок не видаляється, а стає неактивним: пізня подія parts.reserved, що
    прийшла після parts.released чи закриття наряду, інакше «воскресила» б
    резерв. synced_at — час останньої застосованої події; старіші ігноруються.
    """

    __tablename__ = "reservations"

    line_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    order_number: Mapped[str | None] = mapped_column(String(16))
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("items.part_id"), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    synced_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    __table_args__ = (
        CheckConstraint("qty >= 0", name="ck_reservations_qty"),
        Index("ix_reservations_order_id", "order_id"),
        Index(
            "ix_reservations_part_active",
            "part_id",
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )


class Movement(Base):
    """Журнал руху: прихід, списання в наряд, інвентаризація. Лише додається."""

    __tablename__ = "movements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("items.part_id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(13, 2), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    order_number: Mapped[str | None] = mapped_column(String(16))
    line_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind in ('receipt', 'issue', 'count_plus', 'count_minus')", name="ck_movements_kind"
        ),
        Index("ix_movements_part", "part_id", "created_at"),
        # Рядок наряду списується один раз, хоч би скільки разів прийшла подія.
        Index(
            "uq_movements_issue_line",
            "line_id",
            unique=True,
            postgresql_where=text("kind = 'issue'"),
            sqlite_where=text("kind = 'issue'"),
        ),
    )

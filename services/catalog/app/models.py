import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LaborRate(Base):
    """
    Вартість нормо-години. Рядок ніколи не змінюється: нова ставка — новий
    рядок із власним effective_from. Так учорашній наряд рахується за
    вчорашньою ставкою.
    """

    __tablename__ = "labor_rates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    amount: Mapped[Decimal] = mapped_column(Numeric(11, 2), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_labor_rates_amount"),
        Index("ix_labor_rates_effective_from", "effective_from"),
    )


class Service(Base):
    """Робота з прайсу: заміна оливи, розвал-сходження, діагностика."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    norm_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    fixed_price: Mapped[Decimal | None] = mapped_column(Numeric(11, 2))

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("norm_hours >= 0", name="ck_services_norm_hours"),
        CheckConstraint("fixed_price is null or fixed_price >= 0", name="ck_services_fixed_price"),
        Index(
            "uq_services_code_active",
            "code",
            unique=True,
            postgresql_where=text("archived_at is null"),
            sqlite_where=text("archived_at is null"),
        ),
        Index("ix_services_category", "category"),
    )


class Part(Base):
    """Запчастина з каталогу. Залишки — не тут, а в блоці inventory."""

    __tablename__ = "parts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(11, 2), nullable=False)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_parts_price"),
        CheckConstraint("unit in ('pcs', 'l', 'kg', 'm', 'set')", name="ck_parts_unit"),
        # Один артикул у різних брендів — різні деталі: OC90 є і в MAHLE, і в KNECHT.
        Index(
            "uq_parts_sku_brand_active",
            "sku",
            "brand",
            unique=True,
            postgresql_where=text("archived_at is null"),
            sqlite_where=text("archived_at is null"),
        ),
    )

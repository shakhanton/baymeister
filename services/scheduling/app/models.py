import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    """
    Час завжди з поясом і завжди в UTC — і на вході, і на виході.

    Postgres так і робить, а SQLite у тестах губить пояс. Без цього типу
    порівняння «запис з бази» vs «час із запиту» падає лише в тестах, а
    події йдуть із часом без поясу.
    """

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


# Записи в цих статусах займають пост. Скасований чи неявка — звільняють.
ACTIVE_STATUSES = ("booked", "arrived")


class Bay(Base):
    """Пост: підйомник, яма, стенд. Одна колонка на дошці."""

    __tablename__ = "bays"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "kind in ('lift', 'pit', 'alignment', 'diagnostics', 'wash', 'other')",
            name="ck_bays_kind",
        ),
        Index(
            "uq_bays_name_active",
            "name",
            unique=True,
            postgresql_where=text("archived_at is null"),
            sqlite_where=text("archived_at is null"),
        ),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bay_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("bays.id"), nullable=False)

    # Клієнт і авто живуть у своїх блоках. Тут — посилання й копії для дошки.
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_synced_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    vehicle_label: Mapped[str | None] = mapped_column(String(160))
    vehicle_synced_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    starts_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="booked")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="phone")
    note: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Заборона перетину на рівні бази (EXCLUDE USING gist) — у міграції: SQLite
    # такого не вміє, а тести ганяються на ньому. Сервіс перевіряє й сам.
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointments_period"),
        CheckConstraint(
            "status in ('booked', 'arrived', 'completed', 'cancelled', 'no_show')",
            name="ck_appointments_status",
        ),
        CheckConstraint("source in ('phone', 'walk_in', 'online')", name="ck_appointments_source"),
        Index("ix_appointments_bay_period", "bay_id", "starts_at", "ends_at"),
        Index("ix_appointments_starts_at", "starts_at"),
        Index("ix_appointments_customer_id", "customer_id"),
        Index("ix_appointments_vehicle_id", "vehicle_id"),
    )

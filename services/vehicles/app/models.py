import uuid
from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Власник живе в customers. Тут — посилання і копія для списків.
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    # Час події, з якої взято копію. Старіша подія не перезапише новішу.
    customer_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    vin: Mapped[str | None] = mapped_column(String(17))
    plate: Mapped[str] = mapped_column(String(12), nullable=False)
    make: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(String(2000))
    mileage_km: Mapped[int | None] = mapped_column(Integer)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("year is null or (year >= 1900 and year <= 2100)", name="ck_vehicles_year"),
        CheckConstraint("mileage_km is null or mileage_km >= 0", name="ck_vehicles_mileage"),
        # Унікальність — серед активних. Номер проданого й архівованого авто
        # може перейти на нове, і архів не має цьому заважати.
        Index(
            "uq_vehicles_plate_active",
            "plate",
            unique=True,
            postgresql_where=text("archived_at is null"),
            sqlite_where=text("archived_at is null"),
        ),
        Index(
            "uq_vehicles_vin_active",
            "vin",
            unique=True,
            postgresql_where=text("archived_at is null and vin is not null"),
            sqlite_where=text("archived_at is null and vin is not null"),
        ),
        Index("ix_vehicles_customer_id", "customer_id"),
        Index("ix_vehicles_archived_at", "archived_at"),
    )


class MileageReading(Base):
    __tablename__ = "mileage_readings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    km: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("km >= 0", name="ck_mileage_readings_km"),
        Index("ix_mileage_readings_vehicle_id", "vehicle_id", "recorded_at"),
    )

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # 'individual' | 'company' — перелік у контракті, тут просто рядок з перевіркою
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(254))
    tax_id: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(String(2000))
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("type in ('individual', 'company')", name="ck_customers_type"),
        CheckConstraint(
            "discount_percent >= 0 and discount_percent <= 100",
            name="ck_customers_discount",
        ),
        Index("ix_customers_name", "name"),
        Index("ix_customers_archived_at", "archived_at"),
    )

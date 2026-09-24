"""Початкова схема блоку catalog

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "labor_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_labor_rates_amount"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_labor_rates_effective_from", "labor_rates", ["effective_from"])

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("norm_hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("fixed_price", sa.Numeric(precision=11, scale=2), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("norm_hours >= 0", name="ck_services_norm_hours"),
        sa.CheckConstraint(
            "fixed_price is null or fixed_price >= 0", name="ck_services_fixed_price"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_services_code_active",
        "services",
        ["code"],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )
    op.create_index("ix_services_category", "services", ["category"])

    op.create_table(
        "parts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(length=40), nullable=False),
        sa.Column("brand", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=11, scale=2), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("price >= 0", name="ck_parts_price"),
        sa.CheckConstraint("unit in ('pcs', 'l', 'kg', 'm', 'set')", name="ck_parts_unit"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_parts_sku_brand_active",
        "parts",
        ["sku", "brand"],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )


def downgrade() -> None:
    op.drop_index("uq_parts_sku_brand_active", table_name="parts")
    op.drop_table("parts")
    op.drop_index("ix_services_category", table_name="services")
    op.drop_index("uq_services_code_active", table_name="services")
    op.drop_table("services")
    op.drop_index("ix_labor_rates_effective_from", table_name="labor_rates")
    op.drop_table("labor_rates")

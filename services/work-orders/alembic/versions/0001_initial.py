"""Початкова схема блоку work-orders

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


def upgrade() -> None:
    op.create_table(
        "order_counters",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column("customer_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_label", sa.String(length=160), nullable=False),
        sa.Column("vehicle_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("complaint", sa.String(length=2000), nullable=True),
        sa.Column("mileage_km", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('open', 'in_progress', 'done', 'closed', 'cancelled')",
            name="ck_orders_status",
        ),
        sa.CheckConstraint(
            "discount_percent >= 0 and discount_percent <= 100", name="ck_orders_discount"
        ),
        sa.CheckConstraint("mileage_km is null or mileage_km >= 0", name="ck_orders_mileage"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_vehicle_id", "orders", ["vehicle_id"])
    op.create_index("ix_orders_opened_at", "orders", ["opened_at"])

    op.create_table(
        "order_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("catalog_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=110), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=8), nullable=False),
        sa.Column("qty", sa.Numeric(precision=9, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.CheckConstraint("kind in ('service', 'part')", name="ck_order_lines_kind"),
        sa.CheckConstraint("qty > 0", name="ck_order_lines_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_order_lines_price"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_order_lines_order_id", table_name="order_lines")
    op.drop_table("order_lines")
    op.drop_index("ix_orders_opened_at", table_name="orders")
    op.drop_index("ix_orders_vehicle_id", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_table("orders")
    op.drop_table("order_counters")

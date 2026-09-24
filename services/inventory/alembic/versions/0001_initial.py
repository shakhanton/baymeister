"""Початкова схема блоку inventory

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
        "items",
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(length=40), nullable=False),
        sa.Column("brand", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=8), nullable=False),
        sa.Column("catalog_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=20), nullable=True),
        sa.Column("min_qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("min_qty >= 0", name="ck_items_min_qty"),
        sa.PrimaryKeyConstraint("part_id"),
    )

    op.create_table(
        "lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qty_received", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("qty_left", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.CheckConstraint("qty_received > 0", name="ck_lots_received"),
        sa.CheckConstraint("qty_left >= 0 and qty_left <= qty_received", name="ck_lots_left"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_lots_cost"),
        sa.CheckConstraint("source in ('receipt', 'count')", name="ck_lots_source"),
        sa.ForeignKeyConstraint(["part_id"], ["items.part_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lots_fifo",
        "lots",
        ["part_id", "received_at"],
        postgresql_where=sa.text("qty_left > 0"),
    )

    op.create_table(
        "reservations",
        sa.Column("line_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(length=16), nullable=True),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty >= 0", name="ck_reservations_qty"),
        sa.ForeignKeyConstraint(["part_id"], ["items.part_id"]),
        sa.PrimaryKeyConstraint("line_id"),
    )
    op.create_index("ix_reservations_order_id", "reservations", ["order_id"])
    op.create_index(
        "ix_reservations_part_active",
        "reservations",
        ["part_id"],
        postgresql_where=sa.text("active"),
    )

    op.create_table(
        "movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("cost", sa.Numeric(precision=13, scale=2), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("order_number", sa.String(length=16), nullable=True),
        sa.Column("line_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind in ('receipt', 'issue', 'count_plus', 'count_minus')", name="ck_movements_kind"
        ),
        sa.ForeignKeyConstraint(["part_id"], ["items.part_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_movements_part", "movements", ["part_id", "created_at"])
    op.create_index(
        "uq_movements_issue_line",
        "movements",
        ["line_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'issue'"),
    )


def downgrade() -> None:
    op.drop_index("uq_movements_issue_line", table_name="movements")
    op.drop_index("ix_movements_part", table_name="movements")
    op.drop_table("movements")
    op.drop_index("ix_reservations_part_active", table_name="reservations")
    op.drop_index("ix_reservations_order_id", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("ix_lots_fifo", table_name="lots")
    op.drop_table("lots")
    op.drop_table("items")

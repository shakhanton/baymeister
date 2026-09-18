"""Початкова схема блоку customers

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
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("tax_id", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
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
        sa.CheckConstraint("type in ('individual', 'company')", name="ck_customers_type"),
        sa.CheckConstraint(
            "discount_percent >= 0 and discount_percent <= 100",
            name="ck_customers_discount",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_archived_at", "customers", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_customers_archived_at", table_name="customers")
    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_table("customers")

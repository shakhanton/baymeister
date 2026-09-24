"""Початкова схема блоку vehicles

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
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column(
            "customer_synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("plate", sa.String(length=12), nullable=False),
        sa.Column("make", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=60), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("mileage_km", sa.Integer(), nullable=True),
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
        sa.CheckConstraint(
            "year is null or (year >= 1900 and year <= 2100)", name="ck_vehicles_year"
        ),
        sa.CheckConstraint("mileage_km is null or mileage_km >= 0", name="ck_vehicles_mileage"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_vehicles_plate_active",
        "vehicles",
        ["plate"],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )
    op.create_index(
        "uq_vehicles_vin_active",
        "vehicles",
        ["vin"],
        unique=True,
        postgresql_where=sa.text("archived_at is null and vin is not null"),
    )
    op.create_index("ix_vehicles_customer_id", "vehicles", ["customer_id"])
    op.create_index("ix_vehicles_archived_at", "vehicles", ["archived_at"])

    op.create_table(
        "mileage_readings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("km", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("km >= 0", name="ck_mileage_readings_km"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mileage_readings_vehicle_id", "mileage_readings", ["vehicle_id", "recorded_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_mileage_readings_vehicle_id", table_name="mileage_readings")
    op.drop_table("mileage_readings")
    op.drop_index("ix_vehicles_archived_at", table_name="vehicles")
    op.drop_index("ix_vehicles_customer_id", table_name="vehicles")
    op.drop_index("uq_vehicles_vin_active", table_name="vehicles")
    op.drop_index("uq_vehicles_plate_active", table_name="vehicles")
    op.drop_table("vehicles")

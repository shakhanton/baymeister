"""Початкова схема блоку scheduling

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


def _stamp(name: str) -> sa.Column[object]:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "bays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.CheckConstraint(
            "kind in ('lift', 'pit', 'alignment', 'diagnostics', 'wash', 'other')",
            name="ck_bays_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_bays_name_active",
        "bays",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bay_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column("customer_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=True),
        sa.Column("vehicle_label", sa.String(length=160), nullable=True),
        sa.Column("vehicle_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_appointments_period"),
        sa.CheckConstraint(
            "status in ('booked', 'arrived', 'completed', 'cancelled', 'no_show')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint(
            "source in ('phone', 'walk_in', 'online')", name="ck_appointments_source"
        ),
        sa.ForeignKeyConstraint(["bay_id"], ["bays.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_appointments_bay_period", "appointments", ["bay_id", "starts_at", "ends_at"]
    )
    op.create_index("ix_appointments_starts_at", "appointments", ["starts_at"])
    op.create_index("ix_appointments_customer_id", "appointments", ["customer_id"])
    op.create_index("ix_appointments_vehicle_id", "appointments", ["vehicle_id"])

    # Головне правило блоку — на рівні бази. Сервіс перевіряє перетин сам, але
    # два одночасні запити можуть обидва пройти перевірку; другий зупинить це.
    # btree_gist — «довірене» розширення: власник бази ставить його без суперюзера.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT ex_appointments_bay_no_overlap
        EXCLUDE USING gist (
            bay_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (status IN ('booked', 'arrived'))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP CONSTRAINT ex_appointments_bay_no_overlap")
    op.drop_index("ix_appointments_vehicle_id", table_name="appointments")
    op.drop_index("ix_appointments_customer_id", table_name="appointments")
    op.drop_index("ix_appointments_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_bay_period", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("uq_bays_name_active", table_name="bays")
    op.drop_table("bays")

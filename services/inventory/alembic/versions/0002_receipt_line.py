"""Прихід від procurement: рядок приходу стає партією один раз

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_movements_receipt_line",
        "movements",
        ["line_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'receipt' and line_id is not null"),
    )


def downgrade() -> None:
    op.drop_index("uq_movements_receipt_line", table_name="movements")

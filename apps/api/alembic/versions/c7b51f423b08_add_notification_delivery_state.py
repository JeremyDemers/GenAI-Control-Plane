"""add notification delivery state

Revision ID: c7b51f423b08
Revises: 9a3f0f8c2d4b
Create Date: 2026-07-14 19:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7b51f423b08"
down_revision: str | None = "9a3f0f8c2d4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("delivery_status", sa.String(length=40), nullable=False, server_default="pending"),
    )
    op.add_column(
        "notifications",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("notifications", sa.Column("delivered_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("notifications", "delivered_at")
    op.drop_column("notifications", "delivery_attempts")
    op.drop_column("notifications", "delivery_status")

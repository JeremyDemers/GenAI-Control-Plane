"""add lifecycle job payload

Revision ID: 9a3f0f8c2d4b
Revises: 61c09ecbe563
Create Date: 2026-07-14 18:58:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a3f0f8c2d4b"
down_revision: str | None = "61c09ecbe563"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lifecycle_jobs",
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("lifecycle_jobs", "payload")

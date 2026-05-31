"""add cookies column to task_runtime

Revision ID: 0002_cookies
Revises: 0001_initial
Create Date: 2026-06-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_cookies"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("task_runtime")}
    if "cookies" not in cols:
        op.add_column(
            "task_runtime",
            sa.Column("cookies", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("task_runtime", "cookies")

"""add task_proxies table

Revision ID: 0004_task_proxies
Revises: 0003_ad_proxy_configs
Create Date: 2026-06-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_task_proxies"
down_revision = "0003_ad_proxy_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_proxies",
        sa.Column("task_id", sa.BigInteger(), primary_key=True),
        sa.Column("proxy_host", sa.String(), nullable=False),
        sa.Column("proxy_port", sa.Integer(), nullable=False),
        sa.Column("proxy_login", sa.String(), nullable=True),
        sa.Column("proxy_password", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("task_proxies")

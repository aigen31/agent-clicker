"""add ad_proxy_configs table + update leasable index

Revision ID: 0003_ad_proxy_configs
Revises: 0002_cookies
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_ad_proxy_configs"
down_revision = "0002_cookies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ad_proxy_configs ---
    # This table can be in external DB if user has appropriate permissions
    op.create_table(
        "ad_proxy_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ad_id", sa.Integer(), unique=True, nullable=False, index=True),
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

    # --- update leasable status index (was 'created','scheduled' → now 'created','pending') ---
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_indexes = {i["name"] for i in insp.get_indexes("tasks")}
    if "ix_tasks_ready" in existing_indexes:
        op.drop_index("ix_tasks_ready", table_name="tasks")
    op.create_index(
        "ix_tasks_ready",
        "tasks",
        ["exec_time"],
        postgresql_where=sa.text("status IN ('created','pending')"),
    )


def downgrade() -> None:
    op.drop_table("ad_proxy_configs")
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_indexes = {i["name"] for i in insp.get_indexes("tasks")}
    if "ix_tasks_ready" in existing_indexes:
        op.drop_index("ix_tasks_ready", table_name="tasks")
    op.create_index(
        "ix_tasks_ready",
        "tasks",
        ["exec_time"],
        postgresql_where=sa.text("status IN ('created','scheduled')"),
    )

"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-29

Creates both the external schema mirror (tasks, ads — for dev) and the internal
service-owned tables (task_runtime, settings). In production, only the internal
tables are applied because the external schema already exists and is owned by
another team. The migration is idempotent thanks to `IF NOT EXISTS`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    # ---- external (mirrors production, only if missing — dev convenience) ----
    if "ads" not in existing:
        op.create_table(
            "ads",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.Text(), nullable=True),
        )
    if "tasks" not in existing:
        op.create_table(
            "tasks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ad_id", sa.Integer(), sa.ForeignKey("ads.id"), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="created"),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("link", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now()),
            sa.Column("exec_time", sa.DateTime(timezone=False), nullable=True),
        )
        op.create_index("ix_tasks_status_exec_time", "tasks", ["status", "exec_time"])
        op.create_index(
            "ix_tasks_ready",
            "tasks",
            ["exec_time"],
            postgresql_where=sa.text("status IN ('created','scheduled')"),
        )

    # ---- internal (service-owned) ----
    op.create_table(
        "task_runtime",
        sa.Column("task_id", sa.BigInteger(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("profile", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_runtime_locked_at", "task_runtime", ["locked_at"])

    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_runtime_locked_at", table_name="task_runtime")
    op.drop_table("task_runtime")
    # External tables are NOT dropped — they're owned by another team in prod.

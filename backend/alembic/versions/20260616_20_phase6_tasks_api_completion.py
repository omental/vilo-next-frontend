"""phase6 tasks api completion

Revision ID: 20260616_20
Revises: 20260616_19
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_20"
down_revision: Union[str, None] = "20260616_19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("client_id", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("task_type", sa.String(length=50), nullable=False, server_default="general"))
    op.add_column("tasks", sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_tasks_client_id"), "tasks", ["client_id"], unique=False)
    op.create_foreign_key("fk_tasks_client_id_clients", "tasks", "clients", ["client_id"], ["id"], ondelete="SET NULL")

    op.execute("UPDATE tasks SET task_type = 'general' WHERE task_type IS NULL")
    op.execute("UPDATE tasks SET status = 'not_started' WHERE lower(status) = 'pending'")
    op.execute("UPDATE tasks SET status = 'completed' WHERE lower(status) = 'cancelled'")

    op.alter_column("tasks", "task_type", server_default=None)
    op.alter_column("tasks", "status", server_default="not_started")


def downgrade() -> None:
    op.alter_column("tasks", "status", server_default="pending")
    op.drop_constraint("fk_tasks_client_id_clients", "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_client_id"), table_name="tasks")
    op.drop_column("tasks", "archived_at")
    op.drop_column("tasks", "notes")
    op.drop_column("tasks", "reminder_at")
    op.drop_column("tasks", "task_type")
    op.drop_column("tasks", "client_id")

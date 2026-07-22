"""server-backed active time trackers

Revision ID: 20260722_32
Revises: 20260718_31
Create Date: 2026-07-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260722_32"
down_revision: Union[str, None] = "20260718_31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "active_timers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("billing_type", sa.String(length=30), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_active_timers_user_id"),
    )
    op.create_index(op.f("ix_active_timers_id"), "active_timers", ["id"], unique=False)
    op.create_index(op.f("ix_active_timers_organization_id"), "active_timers", ["organization_id"], unique=False)
    op.create_index(op.f("ix_active_timers_user_id"), "active_timers", ["user_id"], unique=False)
    op.create_index(op.f("ix_active_timers_case_id"), "active_timers", ["case_id"], unique=False)
    op.create_index(op.f("ix_active_timers_client_id"), "active_timers", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_active_timers_client_id"), table_name="active_timers")
    op.drop_index(op.f("ix_active_timers_case_id"), table_name="active_timers")
    op.drop_index(op.f("ix_active_timers_user_id"), table_name="active_timers")
    op.drop_index(op.f("ix_active_timers_organization_id"), table_name="active_timers")
    op.drop_index(op.f("ix_active_timers_id"), table_name="active_timers")
    op.drop_table("active_timers")

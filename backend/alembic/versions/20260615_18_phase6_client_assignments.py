"""phase6 client assignments

Revision ID: 20260615_18
Revises: 20260615_17
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260615_18"
down_revision: Union[str, None] = "20260615_17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "user_id", name="uq_client_assignments_client_user"),
    )
    op.create_index(op.f("ix_client_assignments_id"), "client_assignments", ["id"], unique=False)
    op.create_index(op.f("ix_client_assignments_client_id"), "client_assignments", ["client_id"], unique=False)
    op.create_index(op.f("ix_client_assignments_user_id"), "client_assignments", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_client_assignments_user_id"), table_name="client_assignments")
    op.drop_index(op.f("ix_client_assignments_client_id"), table_name="client_assignments")
    op.drop_index(op.f("ix_client_assignments_id"), table_name="client_assignments")
    op.drop_table("client_assignments")

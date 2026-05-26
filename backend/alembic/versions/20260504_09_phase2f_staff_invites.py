"""phase2f staff invites and admin controls

Revision ID: 20260504_09
Revises: 20260504_08
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260504_09"
down_revision: Union[str, None] = "20260504_08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_invites_id"), "user_invites", ["id"], unique=False)
    op.create_index(op.f("ix_user_invites_organization_id"), "user_invites", ["organization_id"], unique=False)
    op.create_index(op.f("ix_user_invites_email"), "user_invites", ["email"], unique=False)
    op.create_index(op.f("ix_user_invites_token"), "user_invites", ["token"], unique=True)
    op.create_index(op.f("ix_user_invites_invited_by"), "user_invites", ["invited_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_invites_invited_by"), table_name="user_invites")
    op.drop_index(op.f("ix_user_invites_token"), table_name="user_invites")
    op.drop_index(op.f("ix_user_invites_email"), table_name="user_invites")
    op.drop_index(op.f("ix_user_invites_organization_id"), table_name="user_invites")
    op.drop_index(op.f("ix_user_invites_id"), table_name="user_invites")
    op.drop_table("user_invites")

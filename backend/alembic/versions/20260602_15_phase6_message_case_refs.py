"""phase6 message case references

Revision ID: 20260602_15
Revises: 20260602_14
Create Date: 2026-06-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260602_15"
down_revision: Union[str, None] = "20260602_14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_case_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_case_references_id"), "message_case_references", ["id"], unique=False)
    op.create_index(op.f("ix_message_case_references_organization_id"), "message_case_references", ["organization_id"], unique=False)
    op.create_index(op.f("ix_message_case_references_message_id"), "message_case_references", ["message_id"], unique=False)
    op.create_index(op.f("ix_message_case_references_case_id"), "message_case_references", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_message_case_references_case_id"), table_name="message_case_references")
    op.drop_index(op.f("ix_message_case_references_message_id"), table_name="message_case_references")
    op.drop_index(op.f("ix_message_case_references_organization_id"), table_name="message_case_references")
    op.drop_index(op.f("ix_message_case_references_id"), table_name="message_case_references")
    op.drop_table("message_case_references")


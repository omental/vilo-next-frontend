"""phase8b trust transaction engine

Revision ID: 20260617_22
Revises: 20260617_21
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_22"
down_revision: Union[str, None] = "20260617_21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trust_transactions", sa.Column("payee_name", sa.String(length=255), nullable=True))
    op.add_column("trust_transactions", sa.Column("payee_type", sa.String(length=50), nullable=True))
    op.add_column("trust_transactions", sa.Column("adjustment_reason", sa.Text(), nullable=True))
    op.add_column("trust_transactions", sa.Column("adjustment_direction", sa.String(length=20), nullable=True))
    op.add_column("trust_transactions", sa.Column("reversal_of_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_trust_transactions_reversal_of_id",
        "trust_transactions",
        "trust_transactions",
        ["reversal_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_trust_transactions_reversal_of_id"), "trust_transactions", ["reversal_of_id"], unique=False)

    op.add_column("trust_receipts", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trust_receipts", sa.Column("voided_by_id", sa.Integer(), nullable=True))
    op.add_column("trust_receipts", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_trust_receipts_voided_by_id_users",
        "trust_receipts",
        "users",
        ["voided_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_trust_receipts_voided_by_id"), "trust_receipts", ["voided_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trust_receipts_voided_by_id"), table_name="trust_receipts")
    op.drop_constraint("fk_trust_receipts_voided_by_id_users", "trust_receipts", type_="foreignkey")
    op.drop_column("trust_receipts", "void_reason")
    op.drop_column("trust_receipts", "voided_by_id")
    op.drop_column("trust_receipts", "voided_at")

    op.drop_index(op.f("ix_trust_transactions_reversal_of_id"), table_name="trust_transactions")
    op.drop_constraint("fk_trust_transactions_reversal_of_id", "trust_transactions", type_="foreignkey")
    op.drop_column("trust_transactions", "reversal_of_id")
    op.drop_column("trust_transactions", "adjustment_direction")
    op.drop_column("trust_transactions", "adjustment_reason")
    op.drop_column("trust_transactions", "payee_type")
    op.drop_column("trust_transactions", "payee_name")

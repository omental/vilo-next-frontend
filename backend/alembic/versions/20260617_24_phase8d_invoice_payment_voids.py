"""phase8d invoice payment void and reversal workflow

Revision ID: 20260617_24
Revises: 20260617_23
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_24"
down_revision: Union[str, None] = "20260617_23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("operating_transactions", sa.Column("linked_payment_id", sa.Integer(), nullable=True))
    op.add_column("operating_transactions", sa.Column("reversal_of_id", sa.Integer(), nullable=True))
    op.add_column("operating_transactions", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("operating_transactions", sa.Column("voided_by_id", sa.Integer(), nullable=True))
    op.add_column("operating_transactions", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_index(op.f("ix_operating_transactions_linked_payment_id"), "operating_transactions", ["linked_payment_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_reversal_of_id"), "operating_transactions", ["reversal_of_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_voided_by_id"), "operating_transactions", ["voided_by_id"], unique=False)
    op.create_foreign_key(
        "fk_operating_transactions_linked_payment_id_invoice_payments",
        "operating_transactions",
        "invoice_payments",
        ["linked_payment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_operating_transactions_reversal_of_id_operating_transactions",
        "operating_transactions",
        "operating_transactions",
        ["reversal_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_operating_transactions_voided_by_id_users",
        "operating_transactions",
        "users",
        ["voided_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_operating_transactions_voided_by_id_users", "operating_transactions", type_="foreignkey")
    op.drop_constraint("fk_operating_transactions_reversal_of_id_operating_transactions", "operating_transactions", type_="foreignkey")
    op.drop_constraint("fk_operating_transactions_linked_payment_id_invoice_payments", "operating_transactions", type_="foreignkey")
    op.drop_index(op.f("ix_operating_transactions_voided_by_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_reversal_of_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_linked_payment_id"), table_name="operating_transactions")
    op.drop_column("operating_transactions", "void_reason")
    op.drop_column("operating_transactions", "voided_by_id")
    op.drop_column("operating_transactions", "voided_at")
    op.drop_column("operating_transactions", "reversal_of_id")
    op.drop_column("operating_transactions", "linked_payment_id")

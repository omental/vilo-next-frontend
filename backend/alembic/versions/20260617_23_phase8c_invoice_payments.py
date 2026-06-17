"""phase8c invoice payments and trust application

Revision ID: 20260617_23
Revises: 20260617_22
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_23"
down_revision: Union[str, None] = "20260617_22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("payment_source", sa.String(length=20), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("linked_trust_transaction_id", sa.Integer(), nullable=True),
        sa.Column("linked_operating_transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_id", sa.Integer(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_trust_transaction_id"], ["trust_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_operating_transaction_id"], ["operating_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["voided_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_payments_id"), "invoice_payments", ["id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_organization_id"), "invoice_payments", ["organization_id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_invoice_id"), "invoice_payments", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_linked_trust_transaction_id"), "invoice_payments", ["linked_trust_transaction_id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_linked_operating_transaction_id"), "invoice_payments", ["linked_operating_transaction_id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_created_by_id"), "invoice_payments", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_voided_by_id"), "invoice_payments", ["voided_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_payments_voided_by_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_created_by_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_linked_operating_transaction_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_linked_trust_transaction_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_invoice_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_organization_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_id"), table_name="invoice_payments")
    op.drop_table("invoice_payments")

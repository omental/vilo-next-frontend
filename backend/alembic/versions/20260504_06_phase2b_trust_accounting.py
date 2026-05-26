"""phase2b trust accounting

Revision ID: 20260504_06
Revises: 20260504_05
Create Date: 2026-05-04
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260504_06"
down_revision: Union[str, None] = "20260504_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("paid_amount", sa.Numeric(12,2), nullable=False, server_default="0"))
    op.add_column("invoices", sa.Column("balance_due", sa.Numeric(12,2), nullable=False, server_default="0"))

    op.create_table(
        "trust_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("account_number_last4", sa.String(4), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trust_accounts_id"), "trust_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_trust_accounts_organization_id"), "trust_accounts", ["organization_id"], unique=False)

    op.create_table(
        "trust_ledgers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trust_account_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("current_balance", sa.Numeric(12,2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trust_account_id"], ["trust_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trust_account_id", "client_id", "case_id", name="uq_trust_ledger_account_client_case"),
    )
    op.create_index(op.f("ix_trust_ledgers_id"), "trust_ledgers", ["id"], unique=False)
    op.create_index(op.f("ix_trust_ledgers_organization_id"), "trust_ledgers", ["organization_id"], unique=False)
    op.create_index(op.f("ix_trust_ledgers_trust_account_id"), "trust_ledgers", ["trust_account_id"], unique=False)
    op.create_index(op.f("ix_trust_ledgers_client_id"), "trust_ledgers", ["client_id"], unique=False)
    op.create_index(op.f("ix_trust_ledgers_case_id"), "trust_ledgers", ["case_id"], unique=False)

    op.create_table(
        "trust_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trust_account_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trust_account_id"], ["trust_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ledger_id"], ["trust_ledgers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trust_transactions_id"), "trust_transactions", ["id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_organization_id"), "trust_transactions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_trust_account_id"), "trust_transactions", ["trust_account_id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_ledger_id"), "trust_transactions", ["ledger_id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_client_id"), "trust_transactions", ["client_id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_case_id"), "trust_transactions", ["case_id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_invoice_id"), "trust_transactions", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_trust_transactions_created_by"), "trust_transactions", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trust_transactions_created_by"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_invoice_id"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_case_id"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_client_id"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_ledger_id"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_trust_account_id"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_organization_id"), table_name="trust_transactions")
    op.drop_index(op.f("ix_trust_transactions_id"), table_name="trust_transactions")
    op.drop_table("trust_transactions")

    op.drop_index(op.f("ix_trust_ledgers_case_id"), table_name="trust_ledgers")
    op.drop_index(op.f("ix_trust_ledgers_client_id"), table_name="trust_ledgers")
    op.drop_index(op.f("ix_trust_ledgers_trust_account_id"), table_name="trust_ledgers")
    op.drop_index(op.f("ix_trust_ledgers_organization_id"), table_name="trust_ledgers")
    op.drop_index(op.f("ix_trust_ledgers_id"), table_name="trust_ledgers")
    op.drop_table("trust_ledgers")

    op.drop_index(op.f("ix_trust_accounts_organization_id"), table_name="trust_accounts")
    op.drop_index(op.f("ix_trust_accounts_id"), table_name="trust_accounts")
    op.drop_table("trust_accounts")

    op.drop_column("invoices", "balance_due")
    op.drop_column("invoices", "paid_amount")

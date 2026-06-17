"""phase8a legal finance foundation

Revision ID: 20260617_21
Revises: 20260616_20
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_21"
down_revision: Union[str, None] = "20260616_20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trust_accounts", sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"))
    op.add_column("trust_accounts", sa.Column("account_type", sa.String(length=30), nullable=False, server_default="pooled"))
    op.add_column("trust_accounts", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("trust_accounts", sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("trust_accounts", sa.Column("current_balance", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("trust_accounts", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.execute(
        """
        UPDATE trust_accounts
        SET current_balance = COALESCE(ledger_totals.total_balance, 0)
        FROM (
            SELECT trust_account_id, SUM(current_balance) AS total_balance
            FROM trust_ledgers
            GROUP BY trust_account_id
        ) AS ledger_totals
        WHERE ledger_totals.trust_account_id = trust_accounts.id
        """
    )
    op.execute("UPDATE trust_accounts SET is_active = CASE WHEN status = 'active' THEN TRUE ELSE FALSE END")

    op.create_index(
        "uq_trust_accounts_org_currency_default_active",
        "trust_accounts",
        ["organization_id", "currency"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND is_active = true"),
    )

    op.add_column("trust_transactions", sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"))
    op.add_column("trust_transactions", sa.Column("payment_method", sa.String(length=50), nullable=True))
    op.add_column("trust_transactions", sa.Column("reference_number", sa.String(length=100), nullable=True))
    op.add_column("trust_transactions", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trust_transactions", sa.Column("voided_by_id", sa.Integer(), nullable=True))
    op.add_column("trust_transactions", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_trust_transactions_voided_by_id_users",
        "trust_transactions",
        "users",
        ["voided_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_trust_transactions_voided_by_id"), "trust_transactions", ["voided_by_id"], unique=False)

    op.create_table(
        "trust_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trust_transaction_id", sa.Integer(), nullable=False),
        sa.Column("receipt_number", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_id", sa.Integer(), nullable=False),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trust_transaction_id"], ["trust_transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trust_transaction_id"),
    )
    op.create_index(op.f("ix_trust_receipts_id"), "trust_receipts", ["id"], unique=False)
    op.create_index(op.f("ix_trust_receipts_organization_id"), "trust_receipts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_trust_receipts_trust_transaction_id"), "trust_receipts", ["trust_transaction_id"], unique=False)
    op.create_index(op.f("ix_trust_receipts_client_id"), "trust_receipts", ["client_id"], unique=False)
    op.create_index(op.f("ix_trust_receipts_case_id"), "trust_receipts", ["case_id"], unique=False)
    op.create_index(op.f("ix_trust_receipts_issued_by_id"), "trust_receipts", ["issued_by_id"], unique=False)

    op.create_table(
        "trust_reconciliations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trust_account_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("bank_statement_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ledger_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("client_ledger_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("matter_ledger_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("difference", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("prepared_by_id", sa.Integer(), nullable=True),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prepared_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trust_account_id"], ["trust_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trust_reconciliations_id"), "trust_reconciliations", ["id"], unique=False)
    op.create_index(op.f("ix_trust_reconciliations_organization_id"), "trust_reconciliations", ["organization_id"], unique=False)
    op.create_index(op.f("ix_trust_reconciliations_trust_account_id"), "trust_reconciliations", ["trust_account_id"], unique=False)
    op.create_index(op.f("ix_trust_reconciliations_prepared_by_id"), "trust_reconciliations", ["prepared_by_id"], unique=False)

    op.create_table(
        "operating_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operating_accounts_id"), "operating_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_operating_accounts_organization_id"), "operating_accounts", ["organization_id"], unique=False)
    op.create_index(
        "uq_operating_accounts_org_currency_default_active",
        "operating_accounts",
        ["organization_id", "currency"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND is_active = true"),
    )

    op.create_table(
        "operating_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("operating_account_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("linked_invoice_id", sa.Integer(), nullable=True),
        sa.Column("linked_trust_transaction_id", sa.Integer(), nullable=True),
        sa.Column("linked_expense_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["linked_expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_trust_transaction_id"], ["trust_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operating_account_id"], ["operating_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operating_transactions_id"), "operating_transactions", ["id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_organization_id"), "operating_transactions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_operating_account_id"), "operating_transactions", ["operating_account_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_linked_invoice_id"), "operating_transactions", ["linked_invoice_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_linked_trust_transaction_id"), "operating_transactions", ["linked_trust_transaction_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_linked_expense_id"), "operating_transactions", ["linked_expense_id"], unique=False)
    op.create_index(op.f("ix_operating_transactions_created_by_id"), "operating_transactions", ["created_by_id"], unique=False)

    op.create_check_constraint(
        "ck_invoice_line_items_no_trust_categories",
        "invoice_line_items",
        "line_type NOT IN ('trust_deposit', 'retainer_deposit', 'client_funds')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invoice_line_items_no_trust_categories", "invoice_line_items", type_="check")

    op.drop_index(op.f("ix_operating_transactions_created_by_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_linked_expense_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_linked_trust_transaction_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_linked_invoice_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_operating_account_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_organization_id"), table_name="operating_transactions")
    op.drop_index(op.f("ix_operating_transactions_id"), table_name="operating_transactions")
    op.drop_table("operating_transactions")

    op.drop_index("uq_operating_accounts_org_currency_default_active", table_name="operating_accounts")
    op.drop_index(op.f("ix_operating_accounts_organization_id"), table_name="operating_accounts")
    op.drop_index(op.f("ix_operating_accounts_id"), table_name="operating_accounts")
    op.drop_table("operating_accounts")

    op.drop_index(op.f("ix_trust_reconciliations_prepared_by_id"), table_name="trust_reconciliations")
    op.drop_index(op.f("ix_trust_reconciliations_trust_account_id"), table_name="trust_reconciliations")
    op.drop_index(op.f("ix_trust_reconciliations_organization_id"), table_name="trust_reconciliations")
    op.drop_index(op.f("ix_trust_reconciliations_id"), table_name="trust_reconciliations")
    op.drop_table("trust_reconciliations")

    op.drop_index(op.f("ix_trust_receipts_issued_by_id"), table_name="trust_receipts")
    op.drop_index(op.f("ix_trust_receipts_case_id"), table_name="trust_receipts")
    op.drop_index(op.f("ix_trust_receipts_client_id"), table_name="trust_receipts")
    op.drop_index(op.f("ix_trust_receipts_trust_transaction_id"), table_name="trust_receipts")
    op.drop_index(op.f("ix_trust_receipts_organization_id"), table_name="trust_receipts")
    op.drop_index(op.f("ix_trust_receipts_id"), table_name="trust_receipts")
    op.drop_table("trust_receipts")

    op.drop_index(op.f("ix_trust_transactions_voided_by_id"), table_name="trust_transactions")
    op.drop_constraint("fk_trust_transactions_voided_by_id_users", "trust_transactions", type_="foreignkey")
    op.drop_column("trust_transactions", "void_reason")
    op.drop_column("trust_transactions", "voided_by_id")
    op.drop_column("trust_transactions", "voided_at")
    op.drop_column("trust_transactions", "reference_number")
    op.drop_column("trust_transactions", "payment_method")
    op.drop_column("trust_transactions", "currency")

    op.drop_index("uq_trust_accounts_org_currency_default_active", table_name="trust_accounts")
    op.drop_column("trust_accounts", "is_active")
    op.drop_column("trust_accounts", "current_balance")
    op.drop_column("trust_accounts", "opening_balance")
    op.drop_column("trust_accounts", "is_default")
    op.drop_column("trust_accounts", "account_type")
    op.drop_column("trust_accounts", "currency")

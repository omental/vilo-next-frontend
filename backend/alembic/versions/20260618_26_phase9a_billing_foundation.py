"""phase9a billing foundation

Revision ID: 20260618_26
Revises: 20260618_25
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_26"
down_revision: Union[str, None] = "20260618_25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "firm_payment_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("bank_name", sa.String(length=255), nullable=False),
        sa.Column("account_number", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("swift_routing", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("payment_instructions", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_firm_payment_accounts_id"), "firm_payment_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_firm_payment_accounts_organization_id"), "firm_payment_accounts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_firm_payment_accounts_created_by_id"), "firm_payment_accounts", ["created_by_id"], unique=False)
    op.create_index(
        "uq_firm_payment_accounts_org_currency_default_active",
        "firm_payment_accounts",
        ["organization_id", "currency"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND is_active = true"),
    )

    op.add_column("invoices", sa.Column("payment_account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_invoices_payment_account_id"), "invoices", ["payment_account_id"], unique=False)
    op.create_foreign_key(
        "fk_invoices_payment_account_id_firm_payment_accounts",
        "invoices",
        "firm_payment_accounts",
        ["payment_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "billing_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("rate_type", sa.String(length=30), nullable=False),
        sa.Column("role_name", sa.String(length=50), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_billing_rates_id"), "billing_rates", ["id"], unique=False)
    op.create_index(op.f("ix_billing_rates_organization_id"), "billing_rates", ["organization_id"], unique=False)
    op.create_index(op.f("ix_billing_rates_user_id"), "billing_rates", ["user_id"], unique=False)
    op.create_index(op.f("ix_billing_rates_created_by_id"), "billing_rates", ["created_by_id"], unique=False)

    op.add_column("time_entries", sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"))
    op.add_column("time_entries", sa.Column("rate_is_manual", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("invoice_line_items", sa.Column("hours", sa.Numeric(12, 2), nullable=True))
    op.add_column("invoice_line_items", sa.Column("rate", sa.Numeric(12, 2), nullable=True))
    op.add_column("invoice_line_items", sa.Column("staff_user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_invoice_line_items_staff_user_id"), "invoice_line_items", ["staff_user_id"], unique=False)
    op.create_foreign_key(
        "fk_invoice_line_items_staff_user_id_users",
        "invoice_line_items",
        "users",
        ["staff_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE invoice_line_items
        SET hours = quantity,
            rate = unit_price
        WHERE time_entry_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoice_line_items_staff_user_id_users", "invoice_line_items", type_="foreignkey")
    op.drop_index(op.f("ix_invoice_line_items_staff_user_id"), table_name="invoice_line_items")
    op.drop_column("invoice_line_items", "staff_user_id")
    op.drop_column("invoice_line_items", "rate")
    op.drop_column("invoice_line_items", "hours")

    op.drop_column("time_entries", "rate_is_manual")
    op.drop_column("time_entries", "currency")

    op.drop_index(op.f("ix_billing_rates_created_by_id"), table_name="billing_rates")
    op.drop_index(op.f("ix_billing_rates_user_id"), table_name="billing_rates")
    op.drop_index(op.f("ix_billing_rates_organization_id"), table_name="billing_rates")
    op.drop_index(op.f("ix_billing_rates_id"), table_name="billing_rates")
    op.drop_table("billing_rates")

    op.drop_constraint("fk_invoices_payment_account_id_firm_payment_accounts", "invoices", type_="foreignkey")
    op.drop_index(op.f("ix_invoices_payment_account_id"), table_name="invoices")
    op.drop_column("invoices", "payment_account_id")

    op.drop_index("uq_firm_payment_accounts_org_currency_default_active", table_name="firm_payment_accounts")
    op.drop_index(op.f("ix_firm_payment_accounts_created_by_id"), table_name="firm_payment_accounts")
    op.drop_index(op.f("ix_firm_payment_accounts_organization_id"), table_name="firm_payment_accounts")
    op.drop_index(op.f("ix_firm_payment_accounts_id"), table_name="firm_payment_accounts")
    op.drop_table("firm_payment_accounts")

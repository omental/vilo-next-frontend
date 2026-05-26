"""phase2a billing foundation

Revision ID: 20260504_05
Revises: 20260504_04
Create Date: 2026-05-04
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260504_05"
down_revision: Union[str, None] = "20260504_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "time_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hours", sa.Numeric(10,2), nullable=False),
        sa.Column("rate", sa.Numeric(12,2), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("billed", sa.Boolean(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_time_entries_id"), "time_entries", ["id"], unique=False)
    op.create_index(op.f("ix_time_entries_organization_id"), "time_entries", ["organization_id"], unique=False)
    op.create_index(op.f("ix_time_entries_case_id"), "time_entries", ["case_id"], unique=False)
    op.create_index(op.f("ix_time_entries_user_id"), "time_entries", ["user_id"], unique=False)

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("billed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expenses_id"), "expenses", ["id"], unique=False)
    op.create_index(op.f("ix_expenses_organization_id"), "expenses", ["organization_id"], unique=False)
    op.create_index(op.f("ix_expenses_case_id"), "expenses", ["case_id"], unique=False)
    op.create_index(op.f("ix_expenses_client_id"), "expenses", ["client_id"], unique=False)
    op.create_index(op.f("ix_expenses_created_by"), "expenses", ["created_by"], unique=False)

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("invoice_number", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(12,2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12,2), nullable=False),
        sa.Column("total", sa.Numeric(12,2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoices_id"), "invoices", ["id"], unique=False)
    op.create_index(op.f("ix_invoices_organization_id"), "invoices", ["organization_id"], unique=False)
    op.create_index(op.f("ix_invoices_client_id"), "invoices", ["client_id"], unique=False)
    op.create_index(op.f("ix_invoices_case_id"), "invoices", ["case_id"], unique=False)
    op.create_index(op.f("ix_invoices_created_by"), "invoices", ["created_by"], unique=False)
    op.create_unique_constraint("uq_invoices_org_invoice_number", "invoices", ["organization_id", "invoice_number"])

    op.create_table(
        "invoice_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12,2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12,2), nullable=False),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("time_entry_id", sa.Integer(), nullable=True),
        sa.Column("expense_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["time_entry_id"], ["time_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_line_items_id"), "invoice_line_items", ["id"], unique=False)
    op.create_index(op.f("ix_invoice_line_items_organization_id"), "invoice_line_items", ["organization_id"], unique=False)
    op.create_index(op.f("ix_invoice_line_items_invoice_id"), "invoice_line_items", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_invoice_line_items_time_entry_id"), "invoice_line_items", ["time_entry_id"], unique=False)
    op.create_index(op.f("ix_invoice_line_items_expense_id"), "invoice_line_items", ["expense_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_line_items_expense_id"), table_name="invoice_line_items")
    op.drop_index(op.f("ix_invoice_line_items_time_entry_id"), table_name="invoice_line_items")
    op.drop_index(op.f("ix_invoice_line_items_invoice_id"), table_name="invoice_line_items")
    op.drop_index(op.f("ix_invoice_line_items_organization_id"), table_name="invoice_line_items")
    op.drop_index(op.f("ix_invoice_line_items_id"), table_name="invoice_line_items")
    op.drop_table("invoice_line_items")

    op.drop_constraint("uq_invoices_org_invoice_number", "invoices", type_="unique")
    op.drop_index(op.f("ix_invoices_created_by"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_case_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_client_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_organization_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_id"), table_name="invoices")
    op.drop_table("invoices")

    op.drop_index(op.f("ix_expenses_created_by"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_client_id"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_case_id"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_organization_id"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_id"), table_name="expenses")
    op.drop_table("expenses")

    op.drop_index(op.f("ix_time_entries_user_id"), table_name="time_entries")
    op.drop_index(op.f("ix_time_entries_case_id"), table_name="time_entries")
    op.drop_index(op.f("ix_time_entries_organization_id"), table_name="time_entries")
    op.drop_index(op.f("ix_time_entries_id"), table_name="time_entries")
    op.drop_table("time_entries")

"""phase8f invoice compliance fields

Revision ID: 20260618_25
Revises: 20260617_24
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_25"
down_revision: Union[str, None] = "20260617_24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"))
    op.add_column("invoices", sa.Column("payment_instructions", sa.Text(), nullable=True))
    op.drop_constraint("ck_invoice_line_items_no_trust_categories", "invoice_line_items", type_="check")
    op.create_check_constraint(
        "ck_invoice_line_items_no_trust_categories",
        "invoice_line_items",
        "line_type NOT IN ('trust_deposit', 'retainer_deposit', 'escrow', 'client_funds', 'property_funds', 'trust_income', 'trust_revenue', 'invoice_retainer')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invoice_line_items_no_trust_categories", "invoice_line_items", type_="check")
    op.create_check_constraint(
        "ck_invoice_line_items_no_trust_categories",
        "invoice_line_items",
        "line_type NOT IN ('trust_deposit', 'retainer_deposit', 'client_funds')",
    )
    op.drop_column("invoices", "payment_instructions")
    op.drop_column("invoices", "currency")

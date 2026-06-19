"""phase10e invoice enforcement

Revision ID: 20260619_28
Revises: 20260619_27
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260619_28"
down_revision: Union[str, None] = "20260619_27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("invoice_tax_label", sa.String(length=50), nullable=False, server_default="GCT"))
    op.add_column("organizations", sa.Column("invoice_tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))

    op.add_column("invoices", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("voided_by_id", sa.Integer(), nullable=True))
    op.add_column("invoices", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_index(op.f("ix_invoices_voided_by_id"), "invoices", ["voided_by_id"], unique=False)
    op.create_foreign_key(
        "fk_invoices_voided_by_id_users",
        "invoices",
        "users",
        ["voided_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_voided_by_id_users", "invoices", type_="foreignkey")
    op.drop_index(op.f("ix_invoices_voided_by_id"), table_name="invoices")
    op.drop_column("invoices", "void_reason")
    op.drop_column("invoices", "voided_by_id")
    op.drop_column("invoices", "voided_at")

    op.drop_column("organizations", "invoice_tax_rate")
    op.drop_column("organizations", "invoice_tax_label")

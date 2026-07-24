"""manual invoice recipients

Revision ID: 20260724_35
Revises: 20260724_34
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_35"
down_revision: Union[str, None] = "20260724_34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("manual_client_name", sa.String(length=255), nullable=True))
    op.alter_column("invoices", "client_id", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_invoices_exactly_one_billing_recipient",
        "invoices",
        "(client_id IS NOT NULL AND manual_client_name IS NULL) OR "
        "(client_id IS NULL AND manual_client_name IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invoices_exactly_one_billing_recipient", "invoices", type_="check")
    # The application never creates a Client record for a manual invoice recipient.
    # A downgrade cannot safely invent that relationship, so it must be blocked until
    # manual-recipient invoices have been handled explicitly by an operator.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM invoices WHERE client_id IS NULL) THEN
            RAISE EXCEPTION 'Cannot downgrade while manual-recipient invoices exist';
          END IF;
        END
        $$;
        """
    )
    op.alter_column("invoices", "client_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("invoices", "manual_client_name")

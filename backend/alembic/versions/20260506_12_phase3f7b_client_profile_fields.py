"""phase3f7b client profile typed fields

Revision ID: 20260506_12
Revises: 20260505_11
Create Date: 2026-05-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260506_12"
down_revision: Union[str, None] = "20260505_11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("client_type", sa.String(length=50), nullable=True))
    op.add_column("clients", sa.Column("trn_no", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("preferred_contact_method", sa.String(length=50), nullable=True))
    op.add_column("clients", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("clients", sa.Column("billing_currency", sa.String(length=10), nullable=True))
    op.add_column("clients", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE clients SET client_type = 'individual' WHERE client_type IS NULL")
    op.execute("UPDATE clients SET billing_currency = 'USD' WHERE billing_currency IS NULL")

    op.alter_column("clients", "client_type", existing_type=sa.String(length=50), nullable=False)


def downgrade() -> None:
    op.drop_column("clients", "archived_at")
    op.drop_column("clients", "billing_currency")
    op.drop_column("clients", "date_of_birth")
    op.drop_column("clients", "preferred_contact_method")
    op.drop_column("clients", "trn_no")
    op.drop_column("clients", "client_type")

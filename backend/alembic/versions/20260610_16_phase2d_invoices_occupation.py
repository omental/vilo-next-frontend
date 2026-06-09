"""phase2d invoices occupation

Revision ID: 20260610_16
Revises: 20260602_15
Create Date: 2026-06-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_16"
down_revision: Union[str, None] = "20260602_15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("occupation", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "occupation")

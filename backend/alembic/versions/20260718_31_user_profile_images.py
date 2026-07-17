"""user profile images

Revision ID: 20260718_31
Revises: 20260718_30
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_31"
down_revision: Union[str, None] = "20260718_30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_image_path", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("profile_image_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "profile_image_updated_at")
    op.drop_column("users", "profile_image_path")

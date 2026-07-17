"""uat reminders and notification dedupe

Revision ID: 20260718_30
Revises: 20260620_29
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_30"
down_revision: Union[str, None] = "20260620_29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendar_events", sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_notifications_org_user_dedupe",
        "notifications",
        ["organization_id", "user_id", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_notifications_org_user_dedupe", "notifications", type_="unique")
    op.drop_column("notifications", "dedupe_key")
    op.drop_column("calendar_events", "reminder_at")

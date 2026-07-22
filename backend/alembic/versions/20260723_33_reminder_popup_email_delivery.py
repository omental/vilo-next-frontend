"""reminder popup and email delivery state

Revision ID: 20260723_33
Revises: 20260722_32
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_33"
down_revision: Union[str, None] = "20260722_32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMINDER_TYPES = "'task_reminder','task_due','task_overdue','event_reminder','event_due'"


def upgrade() -> None:
    op.add_column("notifications", sa.Column("popup_dismissed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("email_status", sa.String(length=20), nullable=True))
    op.add_column("notifications", sa.Column("email_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("notifications", sa.Column("email_last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("email_last_error", sa.Text(), nullable=True))

    # Historical reminders must remain history only: never pop them up or enqueue email.
    op.execute(
        f"""
        UPDATE notifications
        SET popup_dismissed_at = created_at,
            email_status = NULL
        WHERE type IN ({REMINDER_TYPES})
        """
    )

    op.create_index(
        "ix_notifications_pending_popup",
        "notifications",
        ["organization_id", "user_id", "popup_dismissed_at", "created_at"],
        unique=False,
        postgresql_where=sa.text(f"popup_dismissed_at IS NULL AND type IN ({REMINDER_TYPES})"),
    )
    op.create_index(
        "ix_notifications_email_delivery",
        "notifications",
        ["email_status", "email_last_attempt_at"],
        unique=False,
        postgresql_where=sa.text("email_status IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_email_delivery", table_name="notifications")
    op.drop_index("ix_notifications_pending_popup", table_name="notifications")
    op.drop_column("notifications", "email_last_error")
    op.drop_column("notifications", "email_sent_at")
    op.drop_column("notifications", "email_last_attempt_at")
    op.drop_column("notifications", "email_attempts")
    op.drop_column("notifications", "email_status")
    op.drop_column("notifications", "popup_dismissed_at")

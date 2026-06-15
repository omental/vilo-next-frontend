"""phase2g time entries module

Revision ID: 20260615_17
Revises: 20260610_16
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260615_17"
down_revision: Union[str, None] = "20260610_16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("time_entries", sa.Column("client_id", sa.Integer(), nullable=True))
    op.add_column("time_entries", sa.Column("invoice_id", sa.Integer(), nullable=True))
    op.add_column("time_entries", sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("time_entries", sa.Column("end_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("time_entries", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column("time_entries", sa.Column("billing_type", sa.String(length=30), nullable=True))
    op.add_column("time_entries", sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=True))
    op.add_column("time_entries", sa.Column("amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("time_entries", sa.Column("status", sa.String(length=30), nullable=True))

    op.create_index(op.f("ix_time_entries_client_id"), "time_entries", ["client_id"], unique=False)
    op.create_index(op.f("ix_time_entries_invoice_id"), "time_entries", ["invoice_id"], unique=False)
    op.create_foreign_key("fk_time_entries_client_id_clients", "time_entries", "clients", ["client_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_time_entries_invoice_id_invoices", "time_entries", "invoices", ["invoice_id"], ["id"], ondelete="SET NULL")

    op.execute(
        """
        UPDATE time_entries
        SET client_id = cases.client_id
        FROM cases
        WHERE time_entries.case_id = cases.id
        """
    )
    op.execute(
        """
        UPDATE time_entries
        SET invoice_id = linked.invoice_id
        FROM (
            SELECT time_entry_id, MIN(invoice_id) AS invoice_id
            FROM invoice_line_items
            WHERE time_entry_id IS NOT NULL
            GROUP BY time_entry_id
        ) AS linked
        WHERE linked.time_entry_id = time_entries.id
        """
    )
    op.execute(
        """
        UPDATE time_entries
        SET duration_minutes = CAST(ROUND(COALESCE(hours, 0) * 60) AS INTEGER),
            hourly_rate = rate,
            amount = CASE WHEN billable THEN ROUND(COALESCE(hours, 0) * COALESCE(rate, 0), 2) ELSE 0 END,
            billing_type = CASE
                WHEN billed THEN 'invoiced'
                WHEN billable THEN 'professional_fee'
                ELSE 'non_billable'
            END,
            status = CASE
                WHEN billed OR invoice_id IS NOT NULL THEN 'invoiced'
                WHEN billable THEN 'billable'
                ELSE 'non_billable'
            END
        """
    )

    with op.batch_alter_table("time_entries") as batch_op:
        batch_op.alter_column("case_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("description", existing_type=sa.Text(), nullable=True)
        batch_op.alter_column("billing_type", existing_type=sa.String(length=30), nullable=False)
        batch_op.alter_column("amount", existing_type=sa.Numeric(12, 2), nullable=False)
        batch_op.alter_column("status", existing_type=sa.String(length=30), nullable=False)
        batch_op.drop_column("hours")
        batch_op.drop_column("rate")
        batch_op.drop_column("billable")
        batch_op.drop_column("billed")
        batch_op.drop_column("entry_date")


def downgrade() -> None:
    with op.batch_alter_table("time_entries") as batch_op:
        batch_op.add_column(sa.Column("entry_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("billed", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("rate", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("hours", sa.Numeric(10, 2), nullable=False, server_default="0"))
        batch_op.alter_column("case_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("description", existing_type=sa.Text(), nullable=False)

    op.execute(
        """
        UPDATE time_entries
        SET hours = ROUND(COALESCE(duration_minutes, 0) / 60.0, 2),
            rate = COALESCE(hourly_rate, 0),
            billable = CASE WHEN status IN ('billable', 'invoiced') THEN TRUE ELSE FALSE END,
            billed = CASE WHEN status = 'invoiced' OR invoice_id IS NOT NULL THEN TRUE ELSE FALSE END,
            entry_date = COALESCE(CAST(start_time AS DATE), CAST(created_at AS DATE))
        """
    )

    with op.batch_alter_table("time_entries") as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("amount")
        batch_op.drop_column("hourly_rate")
        batch_op.drop_column("billing_type")
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("end_time")
        batch_op.drop_column("start_time")
        batch_op.drop_constraint("fk_time_entries_invoice_id_invoices", type_="foreignkey")
        batch_op.drop_constraint("fk_time_entries_client_id_clients", type_="foreignkey")
        batch_op.drop_index(op.f("ix_time_entries_invoice_id"))
        batch_op.drop_index(op.f("ix_time_entries_client_id"))
        batch_op.drop_column("invoice_id")
        batch_op.drop_column("client_id")

"""phase10g trust hardening

Revision ID: 20260620_29
Revises: 20260619_28
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260620_29"
down_revision: Union[str, None] = "20260619_28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


trust_transactions = sa.table(
    "trust_transactions",
    sa.column("id", sa.Integer()),
    sa.column("organization_id", sa.Integer()),
    sa.column("transaction_date", sa.Date()),
    sa.column("reference_number", sa.String()),
    sa.column("external_reference_number", sa.String()),
)

trust_receipts = sa.table(
    "trust_receipts",
    sa.column("id", sa.Integer()),
    sa.column("organization_id", sa.Integer()),
    sa.column("trust_transaction_id", sa.Integer()),
    sa.column("receipt_number", sa.String()),
)


def upgrade() -> None:
    op.add_column("trust_transactions", sa.Column("external_reference_number", sa.String(length=100), nullable=True))

    bind = op.get_bind()
    transaction_rows = bind.execute(
        sa.select(
            trust_transactions.c.id,
            trust_transactions.c.transaction_date,
            trust_transactions.c.reference_number,
        )
    ).mappings().all()
    for row in transaction_rows:
        system_reference = f"TRX-{row['transaction_date'].year}-{int(row['id']):06d}"
        bind.execute(
            trust_transactions.update()
            .where(trust_transactions.c.id == row["id"])
            .values(
                reference_number=system_reference,
                external_reference_number=row["reference_number"],
            )
        )

    receipt_rows = bind.execute(
        sa.select(
            trust_receipts.c.id,
            trust_receipts.c.trust_transaction_id,
            trust_receipts.c.receipt_number,
            trust_transactions.c.transaction_date,
        ).select_from(
            trust_receipts.join(trust_transactions, trust_transactions.c.id == trust_receipts.c.trust_transaction_id)
        )
    ).mappings().all()
    for row in receipt_rows:
        receipt_number = row["receipt_number"] or f"TR-{row['transaction_date'].year}-{int(row['trust_transaction_id']):06d}"
        bind.execute(
            trust_receipts.update()
            .where(trust_receipts.c.id == row["id"])
            .values(receipt_number=receipt_number)
        )

    op.alter_column("trust_transactions", "reference_number", existing_type=sa.String(length=100), nullable=False)
    op.create_unique_constraint("uq_trust_transactions_org_reference_number", "trust_transactions", ["organization_id", "reference_number"])
    op.create_unique_constraint("uq_trust_receipts_org_receipt_number", "trust_receipts", ["organization_id", "receipt_number"])


def downgrade() -> None:
    op.drop_constraint("uq_trust_receipts_org_receipt_number", "trust_receipts", type_="unique")
    op.drop_constraint("uq_trust_transactions_org_reference_number", "trust_transactions", type_="unique")
    op.alter_column("trust_transactions", "reference_number", existing_type=sa.String(length=100), nullable=True)
    op.drop_column("trust_transactions", "external_reference_number")

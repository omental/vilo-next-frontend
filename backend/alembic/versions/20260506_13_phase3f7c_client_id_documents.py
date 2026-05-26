"""phase3f7c client id documents support

Revision ID: 20260506_13
Revises: 20260506_12
Create Date: 2026-05-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260506_13"
down_revision: Union[str, None] = "20260506_12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("client_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_documents_client_id_clients",
        "documents",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_documents_client_id"), "documents", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_client_id"), table_name="documents")
    op.drop_constraint("fk_documents_client_id_clients", "documents", type_="foreignkey")
    op.drop_column("documents", "client_id")

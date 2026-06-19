"""phase10 d1 docx edit version metadata

Revision ID: 20260619_27
Revises: 20260618_26
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260619_27"
down_revision: Union[str, None] = "20260618_26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("version_source", sa.String(length=30), nullable=True, server_default="upload"))
    op.add_column("documents", sa.Column("version_note", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("source", sa.String(length=30), nullable=True, server_default="upload"))

    op.execute("UPDATE documents SET version_source = 'upload' WHERE version_source IS NULL")
    op.execute("UPDATE document_versions SET source = 'upload' WHERE source IS NULL")
    op.execute("UPDATE document_versions SET source = 'replace' WHERE version_number > 1")

    op.alter_column("documents", "version_source", existing_type=sa.String(length=30), nullable=False, server_default=None)
    op.alter_column("document_versions", "source", existing_type=sa.String(length=30), nullable=False, server_default=None)


def downgrade() -> None:
    op.drop_column("document_versions", "source")
    op.drop_column("documents", "version_note")
    op.drop_column("documents", "version_source")

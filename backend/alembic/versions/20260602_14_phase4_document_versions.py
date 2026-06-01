"""phase4 document versions

Revision ID: 20260602_14
Revises: 20260506_13
Create Date: 2026-06-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260602_14"
down_revision: Union[str, None] = "20260506_13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_versions_id"), "document_versions", ["id"], unique=False)
    op.create_index(op.f("ix_document_versions_document_id"), "document_versions", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_versions_organization_id"), "document_versions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_document_versions_uploaded_by"), "document_versions", ["uploaded_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_versions_uploaded_by"), table_name="document_versions")
    op.drop_index(op.f("ix_document_versions_organization_id"), table_name="document_versions")
    op.drop_index(op.f("ix_document_versions_document_id"), table_name="document_versions")
    op.drop_index(op.f("ix_document_versions_id"), table_name="document_versions")
    op.drop_table("document_versions")


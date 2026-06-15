"""phase4 precedents backend

Revision ID: 20260616_19
Revises: 20260615_18
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_19"
down_revision: Union[str, None] = "20260615_18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "precedents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("practice_area", sa.String(length=100), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_precedents_id"), "precedents", ["id"], unique=False)
    op.create_index(op.f("ix_precedents_organization_id"), "precedents", ["organization_id"], unique=False)
    op.create_index(op.f("ix_precedents_practice_area"), "precedents", ["practice_area"], unique=False)
    op.create_index(op.f("ix_precedents_document_type"), "precedents", ["document_type"], unique=False)
    op.create_index(op.f("ix_precedents_created_by_id"), "precedents", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_precedents_updated_by_id"), "precedents", ["updated_by_id"], unique=False)
    op.create_index(op.f("ix_precedents_is_archived"), "precedents", ["is_archived"], unique=False)
    op.create_index("ix_precedents_org_practice_area", "precedents", ["organization_id", "practice_area"], unique=False)
    op.create_index("ix_precedents_org_document_type", "precedents", ["organization_id", "document_type"], unique=False)
    op.create_index("ix_precedents_org_archived_created", "precedents", ["organization_id", "is_archived", "created_at"], unique=False)

    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("source_precedent_id", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_documents_source_precedent_id"), ["source_precedent_id"], unique=False)
        batch_op.create_foreign_key("fk_documents_source_precedent_id_precedents", "precedents", ["source_precedent_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_source_precedent_id_precedents", type_="foreignkey")
        batch_op.drop_index(op.f("ix_documents_source_precedent_id"))
        batch_op.drop_column("source_precedent_id")

    op.drop_index("ix_precedents_org_archived_created", table_name="precedents")
    op.drop_index("ix_precedents_org_document_type", table_name="precedents")
    op.drop_index("ix_precedents_org_practice_area", table_name="precedents")
    op.drop_index(op.f("ix_precedents_is_archived"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_updated_by_id"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_created_by_id"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_document_type"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_practice_area"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_organization_id"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_id"), table_name="precedents")
    op.drop_table("precedents")

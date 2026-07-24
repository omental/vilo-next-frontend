"""client change requests: drafts, practice areas, expected case date

Revision ID: 20260724_34
Revises: 20260723_33
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_34"
down_revision: Union[str, None] = "20260723_33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("invoices", "currency", existing_type=sa.String(length=10), server_default="JMD")
    op.add_column("cases", sa.Column("expected_completion_date", sa.Date(), nullable=True))
    op.alter_column("cases", "title", existing_type=sa.String(length=255), nullable=True)
    op.alter_column("cases", "client_id", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_cases_non_draft_required_fields",
        "cases",
        "status = 'draft' OR (title IS NOT NULL AND client_id IS NOT NULL)",
    )

    op.create_table(
        "client_intake_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_client_intake_drafts_id", "client_intake_drafts", ["id"])
    op.create_index("ix_client_intake_drafts_organization_id", "client_intake_drafts", ["organization_id"])
    op.create_index("ix_client_intake_drafts_created_by", "client_intake_drafts", ["created_by"])

    op.create_table(
        "client_intake_draft_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("client_intake_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("draft_id", name="uq_client_intake_draft_attachments_draft_id"),
    )
    op.create_index("ix_client_intake_draft_attachments_id", "client_intake_draft_attachments", ["id"])
    op.create_index("ix_client_intake_draft_attachments_organization_id", "client_intake_draft_attachments", ["organization_id"])
    op.create_index("ix_client_intake_draft_attachments_uploaded_by", "client_intake_draft_attachments", ["uploaded_by"])

    op.create_table(
        "practice_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "normalized_name", name="uq_practice_areas_org_normalized_name"),
    )
    op.create_index("ix_practice_areas_id", "practice_areas", ["id"])
    op.create_index("ix_practice_areas_organization_id", "practice_areas", ["organization_id"])
    op.create_index("ix_practice_areas_org_name", "practice_areas", ["organization_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_practice_areas_org_name", table_name="practice_areas")
    op.drop_index("ix_practice_areas_organization_id", table_name="practice_areas")
    op.drop_index("ix_practice_areas_id", table_name="practice_areas")
    op.drop_table("practice_areas")
    # Temporary attachment files live outside PostgreSQL. Operators should
    # discard/clean intake drafts through the application before downgrading;
    # the migration intentionally removes only their database references.
    op.drop_index("ix_client_intake_draft_attachments_uploaded_by", table_name="client_intake_draft_attachments")
    op.drop_index("ix_client_intake_draft_attachments_organization_id", table_name="client_intake_draft_attachments")
    op.drop_index("ix_client_intake_draft_attachments_id", table_name="client_intake_draft_attachments")
    op.drop_table("client_intake_draft_attachments")
    op.drop_index("ix_client_intake_drafts_created_by", table_name="client_intake_drafts")
    op.drop_index("ix_client_intake_drafts_organization_id", table_name="client_intake_drafts")
    op.drop_index("ix_client_intake_drafts_id", table_name="client_intake_drafts")
    op.drop_table("client_intake_drafts")
    op.drop_constraint("ck_cases_non_draft_required_fields", "cases", type_="check")
    # Revision 33 required these fields. Incomplete drafts are intentionally
    # removed before restoring NOT NULL; valid active/closed/archived cases
    # are never deleted by this downgrade.
    op.execute("DELETE FROM cases WHERE status = 'draft' AND (title IS NULL OR client_id IS NULL)")
    op.alter_column("cases", "client_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("cases", "title", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("cases", "expected_completion_date")
    op.alter_column("invoices", "currency", existing_type=sa.String(length=10), server_default="USD")

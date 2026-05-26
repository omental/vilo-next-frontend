"""phase1b clients and cases core

Revision ID: 20260504_02
Revises: 20260504_01
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260504_02"
down_revision: Union[str, None] = "20260504_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

casestatus_enum = postgresql.ENUM(
    "draft",
    "active",
    "closed",
    "archived",
    name="casestatus",
    create_type=False,
)

casepriority_enum = postgresql.ENUM(
    "low",
    "medium",
    "high",
    name="casepriority",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    casestatus_enum.create(bind, checkfirst=True)
    casepriority_enum.create(bind, checkfirst=True)

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clients_id"), "clients", ["id"], unique=False)
    op.create_index(op.f("ix_clients_organization_id"), "clients", ["organization_id"], unique=False)

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("status", casestatus_enum, nullable=False),
        sa.Column("priority", casepriority_enum, nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cases_id"), "cases", ["id"], unique=False)
    op.create_index(op.f("ix_cases_organization_id"), "cases", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cases_client_id"), "cases", ["client_id"], unique=False)
    op.create_index(op.f("ix_cases_created_by"), "cases", ["created_by"], unique=False)

    op.create_table(
        "case_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_assignments_case_user"),
    )
    op.create_index(op.f("ix_case_assignments_id"), "case_assignments", ["id"], unique=False)
    op.create_index(op.f("ix_case_assignments_case_id"), "case_assignments", ["case_id"], unique=False)
    op.create_index(op.f("ix_case_assignments_user_id"), "case_assignments", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f("ix_case_assignments_user_id"), table_name="case_assignments")
    op.drop_index(op.f("ix_case_assignments_case_id"), table_name="case_assignments")
    op.drop_index(op.f("ix_case_assignments_id"), table_name="case_assignments")
    op.drop_table("case_assignments")

    op.drop_index(op.f("ix_cases_created_by"), table_name="cases")
    op.drop_index(op.f("ix_cases_client_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_organization_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_id"), table_name="cases")
    op.drop_table("cases")

    op.drop_index(op.f("ix_clients_organization_id"), table_name="clients")
    op.drop_index(op.f("ix_clients_id"), table_name="clients")
    op.drop_table("clients")

    casepriority_enum.drop(bind, checkfirst=True)
    casestatus_enum.drop(bind, checkfirst=True)

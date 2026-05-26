"""phase2d client portal

Revision ID: 20260504_07
Revises: 20260504_06
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260504_07"
down_revision: Union[str, None] = "20260504_06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_clients_user_id_users",
        "clients",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_clients_user_id"), "clients", ["user_id"], unique=False)

    op.add_column("documents", sa.Column("visibility", sa.String(length=30), nullable=False, server_default="internal"))

    op.create_table(
        "client_intakes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=100), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("matter_type", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_intakes_id"), "client_intakes", ["id"], unique=False)
    op.create_index(op.f("ix_client_intakes_organization_id"), "client_intakes", ["organization_id"], unique=False)
    op.create_index(op.f("ix_client_intakes_client_id"), "client_intakes", ["client_id"], unique=False)
    op.create_index(op.f("ix_client_intakes_submitted_by"), "client_intakes", ["submitted_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_client_intakes_submitted_by"), table_name="client_intakes")
    op.drop_index(op.f("ix_client_intakes_client_id"), table_name="client_intakes")
    op.drop_index(op.f("ix_client_intakes_organization_id"), table_name="client_intakes")
    op.drop_index(op.f("ix_client_intakes_id"), table_name="client_intakes")
    op.drop_table("client_intakes")

    op.drop_column("documents", "visibility")

    op.drop_index(op.f("ix_clients_user_id"), table_name="clients")
    op.drop_constraint("fk_clients_user_id_users", "clients", type_="foreignkey")
    op.drop_column("clients", "user_id")

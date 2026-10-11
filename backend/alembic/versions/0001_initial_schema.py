"""Initial schema for ALPHA Quant Foundation

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("component", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OK"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_audit_logs_component",
        "system_audit_logs",
        ["component"],
        unique=False,
    )
    op.create_index(
        "ix_system_audit_logs_event_type",
        "system_audit_logs",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_system_audit_logs_event_type", table_name="system_audit_logs")
    op.drop_index("ix_system_audit_logs_component", table_name="system_audit_logs")
    op.drop_table("system_audit_logs")

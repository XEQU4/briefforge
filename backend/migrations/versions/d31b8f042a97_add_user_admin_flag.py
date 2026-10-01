"""add administrator flag, defaulting existing users to non-admin

Revision ID: d31b8f042a97
Revises: c92e6b14d830
"""
from alembic import op
import sqlalchemy as sa


revision = "d31b8f042a97"
down_revision = "c92e6b14d830"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_admin")

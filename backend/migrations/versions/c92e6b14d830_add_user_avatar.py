"""add optional user avatar reference

Revision ID: c92e6b14d830
Revises: a7c39d012b6e
"""
from alembic import op
import sqlalchemy as sa


revision = "c92e6b14d830"
down_revision = "a7c39d012b6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_filename", sa.String(length=37), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_filename")

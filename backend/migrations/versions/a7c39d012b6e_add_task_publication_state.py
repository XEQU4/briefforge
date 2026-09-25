"""add separate task publication state

Revision ID: a7c39d012b6e
Revises: 1a2af20b3075
Create Date: 2026-09-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c39d012b6e"
down_revision: Union[str, None] = "1a2af20b3075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("publication_status", sa.String(length=20), nullable=True))
    op.execute(
        "UPDATE tasks SET publication_status = "
        "CASE WHEN status = 'confirmed' THEN 'published' ELSE 'unpublished' END"
    )
    op.alter_column(
        "tasks",
        "publication_status",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'unpublished'"),
    )
    op.create_check_constraint(
        "ck_tasks_publication_status_allowed",
        "tasks",
        "publication_status IN ('unpublished', 'published', 'archived')",
    )
    op.create_check_constraint(
        "ck_tasks_published_requires_confirmed",
        "tasks",
        "publication_status != 'published' OR status = 'confirmed'",
    )
    op.create_index("ix_tasks_public_catalog", "tasks", ["status", "publication_status"])


def downgrade() -> None:
    # Downgrading drops publication state. The old application exposes every
    # confirmed task, including those intentionally unpublished or archived.
    op.drop_index("ix_tasks_public_catalog", table_name="tasks")
    op.drop_constraint("ck_tasks_published_requires_confirmed", "tasks", type_="check")
    op.drop_constraint("ck_tasks_publication_status_allowed", "tasks", type_="check")
    op.drop_column("tasks", "publication_status")

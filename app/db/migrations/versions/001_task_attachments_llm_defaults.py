"""task attachments + llm provider defaults

Revision ID: 001
Revises:
Create Date: 2026-04-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("attachments", sa.JSON(), nullable=True))

    op.alter_column(
        "users",
        "llm_provider",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        server_default="auto",
    )
    op.alter_column(
        "tasks",
        "llm_provider",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        server_default="auto",
    )


def downgrade() -> None:
    op.alter_column(
        "tasks",
        "llm_provider",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        server_default="anthropic",
    )
    op.alter_column(
        "users",
        "llm_provider",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        server_default="anthropic",
    )
    op.drop_column("tasks", "attachments")

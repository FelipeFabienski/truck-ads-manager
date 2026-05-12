"""add user_id to campaigns

Revision ID: e3c4d5f6a7b8
Revises: d2b3c4e5f6a7
Create Date: 2026-05-11 00:02:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3c4d5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "d2b3c4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_campaigns_user_id", table_name="campaigns")
    op.drop_column("campaigns", "user_id")

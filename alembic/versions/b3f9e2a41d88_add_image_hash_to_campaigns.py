"""add image_hash to campaigns

Revision ID: b3f9e2a41d88
Revises: aad048705c0c
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3f9e2a41d88"
down_revision: Union[str, Sequence[str], None] = "aad048705c0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("image_hash", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "image_hash")

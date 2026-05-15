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
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS "
        "user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_campaigns_user_id ON campaigns (user_id)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_campaigns_user_id"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS user_id"))

"""add is_valid and last_validated_at to meta_credentials

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-05-25 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6f7a8b9c0d1e"
down_revision: Union[str, Sequence[str], None] = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE meta_credentials ADD COLUMN IF NOT EXISTS is_valid BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE meta_credentials ADD COLUMN IF NOT EXISTS last_validated_at TIMESTAMPTZ"
    ))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE meta_credentials DROP COLUMN IF EXISTS last_validated_at"))
    op.execute(sa.text("ALTER TABLE meta_credentials DROP COLUMN IF EXISTS is_valid"))

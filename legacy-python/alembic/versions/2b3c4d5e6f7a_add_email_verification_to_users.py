"""add email verification to users

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-13 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2b3c4d5e6f7a"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_expires_at TIMESTAMPTZ"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_users_email_verification_token "
        "ON users (email_verification_token)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_email_verification_token"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS email_verification_expires_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS email_verification_token"))

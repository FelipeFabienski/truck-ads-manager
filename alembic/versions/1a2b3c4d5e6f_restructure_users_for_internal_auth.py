"""restructure users for internal auth

Revision ID: 1a2b3c4d5e6f
Revises: f4e5d6c7b8a9
Create Date: 2026-05-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f4e5d6c7b8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR"))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true"
    ))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    ))

    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS access_token_enc"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS token_expires_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS active_ad_account_id"))

    op.execute(sa.text(
        "UPDATE users SET email = 'unknown_' || id || '@placeholder.invalid' WHERE email IS NULL"
    ))
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'email' AND is_nullable = 'YES'
            ) THEN
                ALTER TABLE users ALTER COLUMN email SET NOT NULL;
            END IF;
        END $$
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_email"))
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'email' AND is_nullable = 'NO'
            ) THEN
                ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
            END IF;
        END $$
    """))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_ad_account_id VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ"
    ))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS access_token_enc VARCHAR"
    ))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS updated_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_verified"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_active"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS password_hash"))

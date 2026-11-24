"""remove facebook oauth

Revision ID: f4e5d6c7b8a9
Revises: e3c4d5f6a7b8
Create Date: 2026-05-07 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4e5d6c7b8a9"
down_revision: Union[str, Sequence[str], None] = "e3c4d5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS meta_ad_accounts"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS facebook_user_id"))
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'access_token_enc'
            ) THEN
                ALTER TABLE users ALTER COLUMN access_token_enc DROP NOT NULL;
            END IF;
        END $$
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'access_token_enc'
            ) THEN
                ALTER TABLE users ALTER COLUMN access_token_enc SET NOT NULL;
            END IF;
        END $$
    """))
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS facebook_user_id VARCHAR"
    ))
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS meta_ad_accounts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ad_account_id VARCHAR NOT NULL,
            account_name VARCHAR,
            currency VARCHAR,
            account_status INTEGER
        )
    """))

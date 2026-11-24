"""create users table

Revision ID: c1a2b3d4e5f6
Revises: b3f9e2a41d88
Create Date: 2026-05-11 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b3f9e2a41d88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old Facebook OAuth schema — later migrations transform this into the current schema.
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            facebook_user_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            email VARCHAR,
            access_token_enc VARCHAR NOT NULL,
            token_expires_at TIMESTAMPTZ,
            active_ad_account_id VARCHAR,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_facebook_user_id ON users (facebook_user_id)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS users"))

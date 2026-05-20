"""add meta credentials

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-05-20 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, Sequence[str], None] = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS meta_credentials (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR NOT NULL,
            access_token_enc VARCHAR NOT NULL,
            ad_account_id VARCHAR NOT NULL,
            page_id VARCHAR,
            instagram_actor_id VARCHAR,
            whatsapp_phone_number VARCHAR,
            whatsapp_business_account_id VARCHAR,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_meta_credentials_user_id"
        " ON meta_credentials (user_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_meta_credentials_id"
        " ON meta_credentials (id)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS meta_credentials"))

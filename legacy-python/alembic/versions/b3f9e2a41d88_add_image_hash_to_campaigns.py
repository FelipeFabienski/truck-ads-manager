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
    # Safety: recreate campaigns in case root migration was a no-op on prod.
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id SERIAL PRIMARY KEY,
            campaign_id VARCHAR NOT NULL,
            external_ad_id VARCHAR,
            modelo VARCHAR NOT NULL,
            cor VARCHAR NOT NULL,
            ano VARCHAR NOT NULL,
            preco VARCHAR,
            km VARCHAR,
            cidade VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'rascunho',
            budget DOUBLE PRECISION NOT NULL,
            leads INTEGER DEFAULT 0,
            spend DOUBLE PRECISION DEFAULT 0.0,
            targeting_data JSON,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_campaigns_campaign_id ON campaigns (campaign_id)"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS image_hash VARCHAR"
    ))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS image_hash"))

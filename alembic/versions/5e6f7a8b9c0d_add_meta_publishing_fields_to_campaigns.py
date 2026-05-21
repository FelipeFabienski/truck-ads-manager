"""add meta publishing fields to campaigns

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-05-21 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5e6f7a8b9c0d"
down_revision: Union[str, Sequence[str], None] = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS"
        " meta_credential_id INTEGER REFERENCES meta_credentials(id) ON DELETE SET NULL"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS meta_campaign_id VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS meta_adset_id VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS meta_creative_id VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS meta_ad_id VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS meta_status VARCHAR"
    ))
    op.execute(sa.text(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_campaigns_meta_credential_id"
        " ON campaigns (meta_credential_id)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_campaigns_meta_credential_id"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS published_at"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS meta_status"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS meta_ad_id"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS meta_creative_id"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS meta_adset_id"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS meta_campaign_id"))
    op.execute(sa.text("ALTER TABLE campaigns DROP COLUMN IF EXISTS meta_credential_id"))

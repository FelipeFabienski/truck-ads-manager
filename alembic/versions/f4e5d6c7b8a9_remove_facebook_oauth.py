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
    op.drop_table("meta_ad_accounts")
    op.drop_column("users", "facebook_user_id")
    op.alter_column("users", "access_token_enc", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "access_token_enc", existing_type=sa.String(), nullable=False, server_default="")
    op.add_column(
        "users",
        sa.Column("facebook_user_id", sa.String(), nullable=True),
    )
    op.create_table(
        "meta_ad_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ad_account_id", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("account_status", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

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
    # Add new auth columns
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Remove Facebook OAuth columns
    op.drop_column("users", "access_token_enc")
    op.drop_column("users", "token_expires_at")
    op.drop_column("users", "active_ad_account_id")

    # Ensure email is NOT NULL and has a unique index
    op.execute("UPDATE users SET email = 'unknown_' || id || '@placeholder.invalid' WHERE email IS NULL")
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)
    op.add_column(
        "users",
        sa.Column("active_ad_account_id", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("access_token_enc", sa.String(), nullable=True),
    )
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_verified")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")

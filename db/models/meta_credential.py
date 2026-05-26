from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class MetaCredential(Base):
    __tablename__ = "meta_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(String(), nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(), nullable=False)
    page_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    instagram_actor_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    whatsapp_phone_number: Mapped[str | None] = mapped_column(String(), nullable=True)
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<MetaCredential {self.id} | user={self.user_id} | {self.name}>"

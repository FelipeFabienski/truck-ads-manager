from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class MetaAdAccount(Base):
    __tablename__ = "meta_ad_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ad_account_id: Mapped[str] = mapped_column()
    account_name: Mapped[str | None] = mapped_column(nullable=True)
    currency: Mapped[str | None] = mapped_column(nullable=True)
    account_status: Mapped[int | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<MetaAdAccount {self.ad_account_id} | user={self.user_id}>"

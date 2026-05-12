from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class CampaignModel(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[str] = mapped_column(unique=True, index=True)
    external_id: Mapped[str | None] = mapped_column("external_ad_id")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    modelo: Mapped[str] = mapped_column()
    cor: Mapped[str] = mapped_column()
    ano: Mapped[str] = mapped_column()
    preco: Mapped[str | None] = mapped_column()
    km: Mapped[str | None] = mapped_column()
    cidade: Mapped[str] = mapped_column()
    image_hash: Mapped[str | None] = mapped_column(default=None)

    status: Mapped[str] = mapped_column(default="rascunho")
    budget: Mapped[float] = mapped_column()
    leads: Mapped[int | None] = mapped_column(default=0)
    spend: Mapped[float | None] = mapped_column(default=0.0)

    targeting_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.campaign_id} | {self.modelo} | {self.status}>"

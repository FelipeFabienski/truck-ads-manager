from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class CampaignModel(Base):
    """Registro persistente de uma campanha no SaaS.

    campaign_id    — identificador público da API (gerado por nós, ex: cmp_a1b2c3d4e5)
    external_id    — ID retornado pela plataforma de anúncios (Meta Ads / mock)
    targeting_data — snapshot do público configurado no momento da criação (JSONB)
    """

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[str] = mapped_column(unique=True, index=True)
    # Python attr: external_id — DB column kept as external_ad_id (no migration needed)
    external_id: Mapped[str | None] = mapped_column("external_ad_id")

    modelo: Mapped[str] = mapped_column()
    cor: Mapped[str] = mapped_column()
    ano: Mapped[str] = mapped_column()
    preco: Mapped[str | None] = mapped_column()
    km: Mapped[str | None] = mapped_column()
    cidade: Mapped[str] = mapped_column()

    status: Mapped[str] = mapped_column(default="rascunho")
    budget: Mapped[float] = mapped_column()
    leads: Mapped[int | None] = mapped_column(default=0)
    spend: Mapped[float | None] = mapped_column(default=0.0)

    image_hash: Mapped[str | None] = mapped_column(default=None)
    targeting_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # default Python-side garante que created_at está sempre disponível após
    # session.refresh(), inclusive em testes com SQLite (sem server_default).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.campaign_id} | {self.modelo} | {self.status}>"

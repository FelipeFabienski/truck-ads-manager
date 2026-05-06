from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base


class CampaignModel(Base):
    """Registro persistente de uma campanha no SaaS.

    campaign_id  — identificador público da API (gerado por nós, ex: cmp_a1b2c3d4e5)
    external_ad_id — ID retornado pela plataforma de anúncios (Meta Ads / mock)
    targeting_data — snapshot do público configurado no momento da criação (JSONB)
    """

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String, unique=True, nullable=False, index=True)
    external_ad_id = Column(String, nullable=True)

    modelo = Column(String, nullable=False)
    cor = Column(String, nullable=False)
    ano = Column(String, nullable=False)
    preco = Column(String, nullable=True)
    km = Column(String, nullable=True)
    cidade = Column(String, nullable=False)

    status = Column(String, nullable=False, default="rascunho")
    budget = Column(Float, nullable=False)
    leads = Column(Integer, default=0)
    spend = Column(Float, default=0.0)

    targeting_data = Column(JSONB, nullable=True)

    # default Python-side garante que created_at está sempre disponível após
    # session.refresh(), inclusive em testes com SQLite (sem server_default).
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.campaign_id} | {self.modelo} | {self.status}>"

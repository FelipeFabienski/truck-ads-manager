from __future__ import annotations

from pydantic import BaseModel, Field


class CampaignListItem(BaseModel):
    """Item retornado por GET /ads/truck — compatível com renderCampanhas()."""

    id: int = Field(description="Timestamp-ms usado como ID de exibição")
    campaign_id: str = Field(description="ID interno do provider")
    modelo: str
    cor: str
    ano: str
    cidade: str
    preco: str
    km: str
    status: str = Field(description="rascunho | ativo | pausado")
    leads: int
    spend: float
    created: str = Field(description="DD/MM/AAAA")
    wpp: str = Field(default="", description="Número WhatsApp do vendedor")
    meta_campaign_id: str | None = Field(default=None, description="ID da campanha na Meta")
    meta_status: str | None = Field(default=None, description="Status Meta: PAUSED | ACTIVE")


class StatusUpdateResponse(BaseModel):
    """Retornado por PATCH /ads/truck/{id}/pausar e /ativar."""

    campaign_id: str
    status: str = Field(description="Novo status em PT: pausado | ativo")
    meta_status: str | None = Field(default=None, description="Status Meta confirmado: ACTIVE | PAUSED")


class DeleteResponse(BaseModel):
    """Retornado por DELETE /ads/truck/{id}."""

    deleted: bool
    campaign_id: str


class MetricsResponse(BaseModel):
    """Retornado por GET /ads/truck/{id}/metricas."""

    campaign_id: str
    impressions: int
    reach: int
    clicks: int
    leads: int
    spent: float
    cpl: float | None
    cpc: float | None
    cpm: float | None
    ctr: float | None
    source: str
    synced_at: str
    period: str


class ErrorResponse(BaseModel):
    """Formato padrão de erro retornado pelos exception handlers."""

    error: bool = True
    code: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    provider: str


class PublishCampaignRequest(BaseModel):
    meta_credential_id: int = Field(..., description="ID da credencial Meta do usuário")


class PublishCampaignResponse(BaseModel):
    campaign_id: str
    meta_campaign_id: str | None
    meta_adset_id: str | None
    meta_creative_id: str | None
    meta_ad_id: str | None
    meta_status: str
    status: str

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


class StatusUpdateResponse(BaseModel):
    """Retornado por PATCH /ads/truck/{id}/pausar e /ativar."""

    campaign_id: str
    status: str = Field(description="Novo status em PT: pausado | ativo")


class DeleteResponse(BaseModel):
    """Retornado por DELETE /ads/truck/{id}."""

    deleted: bool
    campaign_id: str


class MetricsResponse(BaseModel):
    """Retornado por GET /ads/truck/{id}/metricas."""

    campaign_id: str
    impressions: int
    clicks: int
    leads: int
    spent: float
    cpl: float
    period: str


class ErrorResponse(BaseModel):
    """Formato padrão de erro retornado pelos exception handlers."""

    error: bool = True
    code: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    provider: str

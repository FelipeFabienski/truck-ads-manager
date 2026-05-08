from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ads.exceptions import AdsError
from ads.truck.adapter import translate_status_to_en
from ads.truck.schemas import TruckAdCreateRequest, TruckAdPublishResponse
from ads.truck.service import TruckAdService

from ..dependencies import get_truck_service
from ..schemas import (
    CampaignListItem,
    DeleteResponse,
    MetricsResponse,
    StatusUpdateResponse,
)

router = APIRouter()


@router.post(
    "/upload",
    summary="Upload imagem do anúncio",
    tags=["Truck Ads"],
    responses={
        200: {"description": "image_hash retornado pela Meta API"},
        400: {"description": "Provider não suporta upload"},
    },
)
def upload_image(
    file: UploadFile = File(..., description="Imagem JPEG ou PNG do caminhão"),
    service: TruckAdService = Depends(get_truck_service),
) -> dict:
    image_bytes = file.file.read()
    try:
        image_hash = service.upload_image(image_bytes, file.filename or "image.jpg")
    except AdsError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    return {"image_hash": image_hash}


@router.post(
    "/",
    response_model=TruckAdPublishResponse,
    status_code=201,
    summary="Criar e publicar anúncio de caminhão",
    responses={
        201: {"description": "Anúncio criado com status 'rascunho'"},
        422: {"description": "Dados inválidos ou erro de criação no provider"},
    },
)
def publish_truck_ad(
    request: TruckAdCreateRequest,
    service: TruckAdService = Depends(get_truck_service),
) -> TruckAdPublishResponse:
    """
    Fluxo completo: valida o formulário → gera copy via IA → cria campanha/adset/ad
    no provider → retorna objeto achatado pronto para o frontend.
    """
    return service.create_and_publish_truck_ad(request)


@router.get(
    "/",
    response_model=list[CampaignListItem],
    summary="Listar campanhas",
)
def list_campaigns(
    status: str | None = Query(
        None,
        description="Filtrar por status: ativo | pausado | rascunho",
    ),
    nome: str | None = Query(None, description="Busca parcial por nome do caminhão"),
    service: TruckAdService = Depends(get_truck_service),
) -> list[dict]:
    """
    Retorna campanhas no formato exato esperado por `renderCampanhas()` no frontend,
    com métricas (leads, spend) embutidas em cada item.
    """
    filters: dict = {}
    if status:
        filters["status"] = translate_status_to_en(status)
    if nome:
        filters["name_contains"] = nome
    return service.list_campaigns_for_frontend(filters or None)


@router.get(
    "/{campaign_id}",
    response_model=CampaignListItem,
    summary="Detalhar campanha",
    responses={404: {"description": "Campanha não encontrada"}},
)
def get_campaign(
    campaign_id: str,
    service: TruckAdService = Depends(get_truck_service),
) -> dict:
    return service.get_campaign_for_frontend(campaign_id)


@router.patch(
    "/{campaign_id}/pausar",
    response_model=StatusUpdateResponse,
    summary="Pausar campanha",
    responses={
        404: {"description": "Campanha não encontrada"},
        409: {"description": "Transição de status inválida"},
    },
)
def pause_campaign(
    campaign_id: str,
    service: TruckAdService = Depends(get_truck_service),
) -> dict:
    return service.pause_campaign(campaign_id)


@router.patch(
    "/{campaign_id}/ativar",
    response_model=StatusUpdateResponse,
    summary="Ativar campanha",
    responses={
        404: {"description": "Campanha não encontrada"},
        409: {"description": "Transição de status inválida"},
    },
)
def activate_campaign(
    campaign_id: str,
    service: TruckAdService = Depends(get_truck_service),
) -> dict:
    return service.activate_campaign(campaign_id)


@router.delete(
    "/{campaign_id}",
    response_model=DeleteResponse,
    summary="Deletar campanha",
    responses={404: {"description": "Campanha não encontrada"}},
)
def delete_campaign(
    campaign_id: str,
    service: TruckAdService = Depends(get_truck_service),
) -> dict:
    return service.delete_campaign(campaign_id)


@router.get(
    "/{campaign_id}/metricas",
    response_model=MetricsResponse,
    summary="Métricas da campanha",
    responses={404: {"description": "Campanha não encontrada"}},
)
def get_metrics(
    campaign_id: str,
    period: str = Query(
        "last_7d",
        description="Período: today | last_7d | last_30d",
        pattern=r"^(today|last_7d|last_30d)$",
    ),
    service: TruckAdService = Depends(get_truck_service),
) -> dict:
    return service.get_campaign_metrics(campaign_id, period)

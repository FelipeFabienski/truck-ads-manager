from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from ..exceptions import AdsError, CampaignNotFound, InvalidTransition
from ..factory import get_ads_provider
from ..provider import AdsProvider
from .adapter import to_frontend_dto, translate_status_to_pt
from .ai_generator import AIGeneratorService, MockAIGenerator
from .schemas import AIGeneratedContent, TruckAdCreateRequest, TruckAdPublishResponse

if TYPE_CHECKING:
    from db.models import CampaignModel
    from db.repository import CampaignRepository

# Transições válidas usando status PT (igual ao armazenado no banco)
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "rascunho": {"ativo"},
    "ativo": {"pausado"},
    "pausado": {"ativo"},
}


class TruckAdService:
    """Orquestrador de domínio para anúncios de caminhões.

    Suporta dois modos de operação:

    Legado (repository=None)
        Estado gerenciado pelo AdsProvider em memória.
        Usado pelos testes unitários e pelo modo demo.

    Produção (repository=CampaignRepository)
        PostgreSQL como fonte de verdade; AdsProvider responsável apenas
        pela comunicação com a plataforma de anúncios (Meta Ads / mock).
    """

    def __init__(
        self,
        provider: AdsProvider | None = None,
        ai_generator: AIGeneratorService | None = None,
        repository: "CampaignRepository | None" = None,
        provider_name: str = "mock",
        **provider_kwargs,
    ) -> None:
        self._provider = provider or get_ads_provider(provider_name, **provider_kwargs)
        self._ai = ai_generator or MockAIGenerator()
        self._repo = repository  # None → modo legado

    # ── Construtores alternativos ──────────────────────────────────────────────

    @classmethod
    def with_mock(cls, ai_generator: AIGeneratorService | None = None) -> "TruckAdService":
        return cls(provider_name="mock", ai_generator=ai_generator)

    @classmethod
    def with_meta(
        cls,
        access_token: str,
        ad_account_id: str,
        ai_generator: AIGeneratorService | None = None,
    ) -> "TruckAdService":
        return cls(
            provider_name="meta",
            access_token=access_token,
            ad_account_id=ad_account_id,
            ai_generator=ai_generator,
        )

    # ── Publicação ─────────────────────────────────────────────────────────────

    def create_and_publish_truck_ad(
        self, request: TruckAdCreateRequest
    ) -> TruckAdPublishResponse:
        ai_content: AIGeneratedContent = self._ai.generate(request)

        if self._repo is not None:
            return self._create_with_db(request, ai_content)

        # ── Modo legado: provider gerencia estado ──────────────────────────────
        payload = self._map_to_provider_payload(request, ai_content)
        result = self._provider.publish_ad(payload)
        return self._build_response(request, ai_content, result)

    def _create_with_db(
        self,
        request: TruckAdCreateRequest,
        ai_content: AIGeneratedContent,
    ) -> TruckAdPublishResponse:
        """Fluxo DB: salva → chama provider → atualiza external_id."""
        campaign_id = f"cmp_{uuid.uuid4().hex[:10]}"

        record = self._repo.create({  # type: ignore[union-attr]
            "campaign_id": campaign_id,
            "modelo": request.modelo,
            "cor": request.cor,
            "ano": request.ano,
            "preco": request.preco or "",
            "km": request.km or "",
            "cidade": f"{request.cidade}, {request.estado}",
            "status": "rascunho",
            "budget": request.budget,
            "targeting_data": {
                "vendedor_nome": request.vendedor_nome,
                "vendedor_wpp": request.vendedor_wpp,
                "idade_min": request.publico_idade_min,
                "idade_max": request.publico_idade_max,
                "raio": request.publico_raio,
                "genero": request.publico_genero,
                "interesses": request.publico_interesses,
                "posicionamentos": request.publico_posicionamentos,
            },
        })

        # Publicação no provider é não-fatal: DB é a fonte de verdade
        try:
            payload = self._map_to_provider_payload(request, ai_content)
            result = self._provider.publish_ad(payload)
            external_id = str(
                result.get("campaign", {}).get("id")
                or result.get("id")
                or ""
            )
            if external_id:
                self._repo.update_external_id(campaign_id, external_id)  # type: ignore[union-attr]
        except Exception:
            pass

        return self._build_response_from_record(request, ai_content, record)

    # ── Listagem ───────────────────────────────────────────────────────────────

    def list_campaigns_for_frontend(
        self, filters: dict | None = None
    ) -> list[dict]:
        if self._repo is not None:
            return self._list_from_db(filters)

        # Modo legado
        campaigns = self._provider.list_campaigns(filters)
        output = []
        for campaign in campaigns:
            metrics = self._safe_get_metrics(campaign["id"])
            output.append(to_frontend_dto(campaign, metrics))
        return output

    def _list_from_db(self, filters: dict | None) -> list[dict]:
        filters = filters or {}
        # Router envia status em EN ("active"); banco armazena em PT ("ativo")
        status_en = filters.get("status")
        status_pt = translate_status_to_pt(status_en) if status_en else None
        nome = filters.get("name_contains")
        records = self._repo.get_all(status=status_pt, nome=nome)  # type: ignore[union-attr]
        return [self._model_to_dto(r) for r in records]

    # ── Controle de estado ─────────────────────────────────────────────────────

    def pause_campaign(self, campaign_id: str) -> dict:
        if self._repo is not None:
            return self._transition(campaign_id, "pausado")
        result = self._provider.pause_campaign(campaign_id)
        return {"campaign_id": result["id"], "status": translate_status_to_pt(result["status"])}

    def activate_campaign(self, campaign_id: str) -> dict:
        if self._repo is not None:
            return self._transition(campaign_id, "ativo")
        result = self._provider.activate_campaign(campaign_id)
        return {"campaign_id": result["id"], "status": translate_status_to_pt(result["status"])}

    def _transition(self, campaign_id: str, target: str) -> dict:
        record = self._repo.get_by_id(campaign_id)  # type: ignore[union-attr]
        if not record:
            raise CampaignNotFound(campaign_id)
        if target not in _VALID_TRANSITIONS.get(record.status, set()):
            raise InvalidTransition(record.status, target)
        self._repo.update_status(campaign_id, target)  # type: ignore[union-attr]
        # Notifica o provider de forma não-fatal
        try:
            action = self._provider.pause_campaign if target == "pausado" else self._provider.activate_campaign
            action(record.external_ad_id or campaign_id)
        except Exception:
            pass
        return {"campaign_id": campaign_id, "status": target}

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_campaign(self, campaign_id: str) -> dict:
        if self._repo is not None:
            record = self._repo.get_by_id(campaign_id)
            if not record:
                raise CampaignNotFound(campaign_id)
            try:
                self._provider.delete_campaign(record.external_ad_id or campaign_id)
            except Exception:
                pass
            self._repo.delete(campaign_id)
            return {"deleted": True, "campaign_id": campaign_id}
        return self._provider.delete_campaign(campaign_id)

    # ── Detalhe e métricas ─────────────────────────────────────────────────────

    def get_campaign_for_frontend(self, campaign_id: str) -> dict:
        if self._repo is not None:
            record = self._repo.get_by_id(campaign_id)
            if not record:
                raise CampaignNotFound(campaign_id)
            return self._model_to_dto(record)
        campaign = self._provider.get_campaign(campaign_id)
        metrics = self._safe_get_metrics(campaign_id)
        return to_frontend_dto(campaign, metrics)

    def get_campaign_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        if self._repo is not None:
            record = self._repo.get_by_id(campaign_id)
            if not record:
                raise CampaignNotFound(campaign_id)
            try:
                return self._provider.get_metrics(
                    record.external_ad_id or campaign_id, period
                )
            except Exception:
                return {
                    "campaign_id": campaign_id,
                    "impressions": 0,
                    "clicks": 0,
                    "leads": record.leads or 0,
                    "spent": record.spend or 0.0,
                    "cpl": 0.0,
                    "period": period,
                }
        return self._provider.get_metrics(campaign_id, period)

    # ── Mapeamento (request + IA) → AdsProvider payload ───────────────────────

    def _map_to_provider_payload(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
    ) -> dict:
        interests = [i.strip() for i in req.publico_interesses.split(",") if i.strip()]
        schedule = self._build_schedule(req.duracao)

        return {
            "campaign": {
                "name": f"{req.modelo} {req.ano} — {req.cidade}, {req.estado}",
                "objective": "OUTCOME_LEADS",
                "budget": req.budget,
                "extra": {
                    "modelo": req.modelo,
                    "cor": req.cor,
                    "ano": req.ano,
                    "preco": req.preco or "",
                    "km": req.km or "",
                    "cidade": req.cidade,
                    "estado": req.estado,
                    "vendedor_nome": req.vendedor_nome,
                    "vendedor_wpp": req.vendedor_wpp,
                },
            },
            "adset": {
                "name": (
                    f"Público {req.cidade} "
                    f"{req.publico_idade_min}-{req.publico_idade_max} anos"
                ),
                "budget": req.budget,
                "schedule": schedule,
                "audience": {
                    "locations": [req.estado],
                    "age_min": req.publico_idade_min,
                    "age_max": req.publico_idade_max,
                    "interests": interests,
                    "gender": req.publico_genero,
                    "radius_km": req.publico_raio,
                },
            },
            "ad": {
                "name": f"Ad — {req.modelo} {req.ano}",
                "copy": ai.copy,
                "headline": ai.headline,
                "creative": {
                    "type": "image",
                    "url": "",
                    "caption": ai.roteiro,
                },
                "destination": f"https://wa.me/{req.vendedor_wpp}",
            },
        }

    # ── Construtores de resposta ───────────────────────────────────────────────

    def _build_response(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
        publish_result: dict,
    ) -> TruckAdPublishResponse:
        """Modo legado — constrói resposta a partir do dict retornado pelo provider."""
        campaign = publish_result.get("campaign", {})
        created_at = campaign.get("created_at") or datetime.now(timezone.utc).isoformat()
        try:
            dt = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            dt = datetime.now(timezone.utc)

        return TruckAdPublishResponse(
            id=int(dt.timestamp() * 1000),
            campaign_id=campaign.get("id", ""),
            status="rascunho",
            modelo=req.modelo,
            cor=req.cor,
            ano=req.ano,
            cidade=f"{req.cidade}, {req.estado}",
            preco=req.preco or "",
            km=req.km or "",
            copy=ai.copy,
            headline=ai.headline,
            roteiro=ai.roteiro,
            budget=req.budget,
            created=dt.strftime("%d/%m/%Y"),
        )

    def _build_response_from_record(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
        record: "CampaignModel",
    ) -> TruckAdPublishResponse:
        """Modo DB — constrói resposta a partir do ORM model."""
        dt = record.created_at or datetime.now(timezone.utc)
        return TruckAdPublishResponse(
            id=int(dt.timestamp() * 1000),
            campaign_id=record.campaign_id,
            status="rascunho",
            modelo=req.modelo,
            cor=req.cor,
            ano=req.ano,
            cidade=record.cidade,
            preco=req.preco or "",
            km=req.km or "",
            copy=ai.copy,
            headline=ai.headline,
            roteiro=ai.roteiro,
            budget=req.budget,
            created=dt.strftime("%d/%m/%Y"),
        )

    def _model_to_dto(self, record: "CampaignModel") -> dict:
        """Converte CampaignModel para o contrato de frontend."""
        dt = record.created_at or datetime.now(timezone.utc)
        return {
            "id": int(dt.timestamp() * 1000),
            "campaign_id": record.campaign_id,
            "modelo": record.modelo,
            "cor": record.cor,
            "ano": record.ano,
            "cidade": record.cidade,
            "preco": record.preco or "",
            "km": record.km or "",
            "status": record.status,
            "leads": record.leads or 0,
            "spend": record.spend or 0.0,
            "created": dt.strftime("%d/%m/%Y"),
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_schedule(duracao: int) -> dict:
        if duracao <= 0:
            return {}
        start = datetime.now(timezone.utc)
        return {
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(days=duracao)).isoformat(),
        }

    def _safe_get_metrics(self, campaign_id: str) -> dict:
        try:
            return self._provider.get_metrics(campaign_id)
        except AdsError:
            return {}

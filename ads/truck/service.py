from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..exceptions import AdsError
from ..factory import get_ads_provider
from ..provider import AdsProvider
from .adapter import to_frontend_dto, translate_status_to_pt
from .ai_generator import AIGeneratorService, MockAIGenerator
from .schemas import AIGeneratedContent, TruckAdCreateRequest, TruckAdPublishResponse


class TruckAdService:
    """
    Orquestrador de domínio para anúncios de caminhões.

    Fluxo de create_and_publish_truck_ad():
        1. Recebe TruckAdCreateRequest do controller
        2. Chama AIGeneratorService → copy, headline, roteiro
        3. Mapeia dados (request + IA) → payload hierárquico do AdsProvider
        4. Chama provider.publish_ad() → Campaign + AdSet + Ad criados
        5. Retorna resposta achatada para o frontend

    O AdsProvider nunca conhece o domínio "caminhão" — essa responsabilidade
    fica nesta classe e no adapter.
    """

    def __init__(
        self,
        provider: AdsProvider | None = None,
        ai_generator: AIGeneratorService | None = None,
        provider_name: str = "mock",
        **provider_kwargs,
    ) -> None:
        self._provider = provider or get_ads_provider(provider_name, **provider_kwargs)
        self._ai = ai_generator or MockAIGenerator()

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
        """
        Ponto de entrada principal chamado pelo endpoint POST /ads/truck.

        Returns:
            TruckAdPublishResponse — objeto achatado pronto para serialização JSON.
        """
        # ── 1. Geração de conteúdo via IA ──────────────────────────────────────
        ai_content: AIGeneratedContent = self._ai.generate(request)

        # ── 2. Mapeamento para payload do AdsProvider ──────────────────────────
        payload = self._map_to_provider_payload(request, ai_content)

        # ── 3. Publicação via provider ─────────────────────────────────────────
        result = self._provider.publish_ad(payload)

        # ── 4. Resposta achatada para o frontend ───────────────────────────────
        return self._build_response(request, ai_content, result)

    # ── Listagem com adapter ───────────────────────────────────────────────────

    def list_campaigns_for_frontend(
        self, filters: dict | None = None
    ) -> list[dict]:
        """
        Lista campanhas já formatadas para o padrão esperado por renderCampanhas().
        Incorpora métricas inline (leads, spend) para cada campanha.
        """
        campaigns = self._provider.list_campaigns(filters)
        output = []
        for campaign in campaigns:
            metrics = self._safe_get_metrics(campaign["id"])
            output.append(to_frontend_dto(campaign, metrics))
        return output

    # ── Controle de estado ─────────────────────────────────────────────────────

    def pause_campaign(self, campaign_id: str) -> dict:
        result = self._provider.pause_campaign(campaign_id)
        return {"campaign_id": result["id"], "status": translate_status_to_pt(result["status"])}

    def activate_campaign(self, campaign_id: str) -> dict:
        result = self._provider.activate_campaign(campaign_id)
        return {"campaign_id": result["id"], "status": translate_status_to_pt(result["status"])}

    def delete_campaign(self, campaign_id: str) -> dict:
        return self._provider.delete_campaign(campaign_id)

    # ── Detalhe e métricas ─────────────────────────────────────────────────────

    def get_campaign_for_frontend(self, campaign_id: str) -> dict:
        campaign = self._provider.get_campaign(campaign_id)
        metrics = self._safe_get_metrics(campaign_id)
        return to_frontend_dto(campaign, metrics)

    def get_campaign_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        return self._provider.get_metrics(campaign_id, period)

    # ── Mapeamento (request + IA) → AdsProvider payload ───────────────────────

    def _map_to_provider_payload(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
    ) -> dict:
        """
        Constrói o dict hierárquico {campaign, adset, ad} que publish_ad() espera.
        Os dados do caminhão ficam em campaign.extra para que o adapter os recupere
        ao listar campanhas — o AdsProvider apenas os armazena de forma opaca.
        """
        interests = [i.strip() for i in req.publico_interesses.split(",") if i.strip()]
        schedule = self._build_schedule(req.duracao)

        return {
            "campaign": {
                "name": f"{req.modelo} {req.ano} — {req.cidade}, {req.estado}",
                "objective": "OUTCOME_LEADS",
                "budget": req.budget,
                # Metadados de domínio — armazenados de forma opaca pelo provider
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

    # ── Construção da resposta achatada ────────────────────────────────────────

    def _build_response(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
        publish_result: dict,
    ) -> TruckAdPublishResponse:
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

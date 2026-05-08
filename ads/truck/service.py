from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from ..exceptions import CampaignNotFound, InvalidTransition
from ..factory import get_ads_provider
from ..provider import AdsProvider
from .adapter import to_frontend_dto, translate_status_to_pt
from .ai_generator import AIGeneratorService, MockAIGenerator
from .schemas import AIGeneratedContent, TruckAdCreateRequest, TruckAdPublishResponse

if TYPE_CHECKING:
    from db.models import CampaignModel
    from db.repository import CampaignRepository

logger = logging.getLogger(__name__)

# Valid status transitions stored in DB (PT — presentation language)
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "rascunho": {"ativo"},
    "ativo": {"pausado"},
    "pausado": {"ativo"},
}


# ── Infrastructure adapter ────────────────────────────────────────────────────

class _ProviderAdapter:
    """Converts domain objects into AdsProvider payloads.

    Isolates the service from the provider's wire format.
    All provider-specific dict structure lives here, not in the service.
    """

    @staticmethod
    def build_payload(req: TruckAdCreateRequest, ai: AIGeneratedContent) -> dict:
        interests = [i.strip() for i in req.publico_interesses.split(",") if i.strip()]
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
                "name": f"Público {req.cidade} {req.publico_idade_min}-{req.publico_idade_max} anos",
                "budget": req.budget,
                "schedule": _ProviderAdapter._schedule(req.duracao),
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
                "copy": ai.ad_copy,
                "headline": ai.headline,
                "creative": {"type": "image", "url": "", "caption": ai.roteiro},
                "destination": f"https://wa.me/{req.vendedor_wpp}",
                "image_hash": req.image_hash,
            },
        }

    @staticmethod
    def extract_external_id(result: dict) -> str:
        return str(
            result.get("campaign", {}).get("id")
            or result.get("id")
            or ""
        )

    @staticmethod
    def _schedule(duracao: int) -> dict:
        if duracao <= 0:
            return {}
        start = datetime.now(timezone.utc)
        return {
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(days=duracao)).isoformat(),
        }


# ── Domain service ────────────────────────────────────────────────────────────

class TruckAdService:
    """Orchestrates truck ad campaigns across the persistence and ads platform layers.

    Two operating modes:

    Legacy (repository=None)
        State managed by AdsProvider in memory.
        Used by unit tests and demo mode.

    Production (repository=CampaignRepository)
        PostgreSQL as source of truth; AdsProvider handles only external platform
        communication. All domain state is read from the DB record after persistence.
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
        self._repo = repository

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

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_and_publish_truck_ad(
        self, request: TruckAdCreateRequest
    ) -> TruckAdPublishResponse:
        ai_content = self._ai.generate(request)
        if self._repo is not None:
            return self._create_with_db(request, ai_content)
        # Legacy: provider manages state in memory
        payload = _ProviderAdapter.build_payload(request, ai_content)
        result = self._provider.publish_ad(payload)
        return self._build_legacy_response(request, ai_content, result)

    def list_campaigns_for_frontend(
        self, filters: dict | None = None
    ) -> list[dict]:
        if self._repo is not None:
            return self._list_from_db(filters)
        campaigns = self._provider.list_campaigns(filters)
        return [
            to_frontend_dto(c, self._safe_get_metrics(c["id"]))
            for c in campaigns
        ]

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

    def delete_campaign(self, campaign_id: str) -> dict:
        if self._repo is not None:
            return self._delete_with_db(campaign_id)
        return self._provider.delete_campaign(campaign_id)

    def get_campaign_for_frontend(self, campaign_id: str) -> dict:
        if self._repo is not None:
            record = self._repo.get_by_id(campaign_id)
            if not record:
                raise CampaignNotFound(campaign_id)
            return self._record_to_dto(record)
        campaign = self._provider.get_campaign(campaign_id)
        return to_frontend_dto(campaign, self._safe_get_metrics(campaign_id))

    def get_campaign_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        if self._repo is not None:
            return self._metrics_from_db(campaign_id, period)
        return self._provider.get_metrics(campaign_id, period)

    # ── DB mode — write path ───────────────────────────────────────────────────

    def _create_with_db(
        self,
        request: TruckAdCreateRequest,
        ai_content: AIGeneratedContent,
    ) -> TruckAdPublishResponse:
        """Persist → publish to provider (non-fatal) → return response from DB record."""
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
            "image_hash": request.image_hash,
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

        # Build response from the fresh record before any further commit expires it
        response = self._build_db_response(ai_content, record)

        # Provider publish is best-effort — DB is the source of truth
        try:
            payload = _ProviderAdapter.build_payload(request, ai_content)
            result = self._provider.publish_ad(payload)
            external_id = _ProviderAdapter.extract_external_id(result)
            if external_id:
                self._repo.update_record_external_id(record, external_id)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning(
                "Provider publish failed for campaign %s — saved as draft. Reason: %s",
                campaign_id, exc,
            )

        return response

    def _transition(self, campaign_id: str, target: str) -> dict:
        record = self._repo.get_by_id(campaign_id)  # type: ignore[union-attr]
        if not record:
            raise CampaignNotFound(campaign_id)
        if target not in _VALID_TRANSITIONS.get(record.status, set()):
            raise InvalidTransition(record.status, target)
        external_id = record.external_id  # capture before commit expires the record
        self._repo.update_record_status(record, target)  # type: ignore[union-attr]
        self._notify_provider_status(external_id or campaign_id, target)
        return {"campaign_id": campaign_id, "status": target}

    def _delete_with_db(self, campaign_id: str) -> dict:
        record = self._repo.get_by_id(campaign_id)  # type: ignore[union-attr]
        if not record:
            raise CampaignNotFound(campaign_id)
        self._notify_provider_delete(record.external_id or campaign_id)
        self._repo.delete_record(record)  # type: ignore[union-attr]
        return {"deleted": True, "campaign_id": campaign_id}

    # ── DB mode — read path ────────────────────────────────────────────────────

    def _list_from_db(self, filters: dict | None) -> list[dict]:
        filters = filters or {}
        # Router sends status in EN ("active"); DB stores in PT ("ativo")
        status_en = filters.get("status")
        status_pt = translate_status_to_pt(status_en) if status_en else None
        records = self._repo.get_all(  # type: ignore[union-attr]
            status=status_pt,
            nome=filters.get("name_contains"),
        )
        return [self._record_to_dto(r) for r in records]

    def _metrics_from_db(self, campaign_id: str, period: str) -> dict:
        record = self._repo.get_by_id(campaign_id)  # type: ignore[union-attr]
        if not record:
            raise CampaignNotFound(campaign_id)
        try:
            return self._provider.get_metrics(record.external_id or campaign_id, period)
        except Exception as exc:
            logger.warning("Provider metrics failed for campaign %s: %s", campaign_id, exc)
            return {
                "campaign_id": campaign_id,
                "impressions": 0,
                "clicks": 0,
                "leads": record.leads or 0,
                "spent": record.spend or 0.0,
                "cpl": 0.0,
                "period": period,
            }

    # ── Provider notifications (best-effort, non-fatal) ────────────────────────

    def _notify_provider_status(self, external_id: str, target: str) -> None:
        try:
            action = (
                self._provider.pause_campaign
                if target == "pausado"
                else self._provider.activate_campaign
            )
            action(external_id)
        except Exception as exc:
            logger.warning(
                "Provider status sync failed for %s → %s: %s", external_id, target, exc
            )

    def _notify_provider_delete(self, external_id: str) -> None:
        try:
            self._provider.delete_campaign(external_id)
        except Exception as exc:
            logger.warning("Provider delete failed for %s: %s", external_id, exc)

    # ── DTO builders ───────────────────────────────────────────────────────────

    def _build_db_response(
        self,
        ai_content: AIGeneratedContent,
        record: "CampaignModel",
    ) -> TruckAdPublishResponse:
        """Builds response from the persisted record — request data is NOT used."""
        dt = record.created_at
        return TruckAdPublishResponse.model_validate({
            "id": int(dt.timestamp() * 1000),
            "campaign_id": record.campaign_id,
            "status": record.status,
            "modelo": record.modelo,
            "cor": record.cor,
            "ano": record.ano,
            "cidade": record.cidade,
            "preco": record.preco or "",
            "km": record.km or "",
            "copy": ai_content.ad_copy,
            "headline": ai_content.headline,
            "roteiro": ai_content.roteiro,
            "budget": record.budget,
            "created": dt.strftime("%d/%m/%Y"),
        })

    def _build_legacy_response(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
        publish_result: dict,
    ) -> TruckAdPublishResponse:
        """Legacy mode — builds response from the provider result dict."""
        campaign = publish_result.get("campaign", {})
        created_at = campaign.get("created_at") or datetime.now(timezone.utc).isoformat()
        try:
            dt = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            dt = datetime.now(timezone.utc)
        return TruckAdPublishResponse.model_validate({
            "id": int(dt.timestamp() * 1000),
            "campaign_id": campaign.get("id", ""),
            "status": "rascunho",
            "modelo": req.modelo,
            "cor": req.cor,
            "ano": req.ano,
            "cidade": f"{req.cidade}, {req.estado}",
            "preco": req.preco or "",
            "km": req.km or "",
            "copy": ai.ad_copy,
            "headline": ai.headline,
            "roteiro": ai.roteiro,
            "budget": req.budget,
            "created": dt.strftime("%d/%m/%Y"),
        })

    def _record_to_dto(self, record: "CampaignModel") -> dict[str, Any]:
        """Converts a CampaignModel to the frontend contract dict."""
        dt = record.created_at
        td: dict[str, Any] = record.targeting_data or {}
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
            "wpp": td.get("vendedor_wpp", ""),
        }

    def upload_image(self, image_bytes: bytes, filename: str = "image.jpg") -> str:
        if not hasattr(self._provider, "upload_image"):
            from ..exceptions import AdsError
            raise AdsError("Provider does not support image upload", "UNSUPPORTED")
        return self._provider.upload_image(image_bytes, filename)  # type: ignore[attr-defined]

    # ── Backward-compatible alias (used by unit tests) ────────────────────────

    def _map_to_provider_payload(
        self,
        req: TruckAdCreateRequest,
        ai: AIGeneratedContent,
    ) -> dict:
        return _ProviderAdapter.build_payload(req, ai)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _safe_get_metrics(self, campaign_id: str) -> dict:
        try:
            return self._provider.get_metrics(campaign_id)
        except Exception as exc:
            logger.warning("Metrics unavailable for campaign %s: %s", campaign_id, exc)
            return {}

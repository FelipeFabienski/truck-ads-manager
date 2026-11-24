from __future__ import annotations

from .exceptions import AdsError
from .factory import get_ads_provider
from .provider import AdsProvider


class AdService:
    """
    Camada de orquestração entre o backend da aplicação e o AdsProvider.

    Responsabilidades:
    - Receber dados do frontend/controllers
    - Invocar geração de copy via IA (stub substituível)
    - Chamar o AdsProvider ativo
    - Ponto de extensão para persistência no banco de dados

    Uso rápido:
        service = AdService.with_mock()
        service = AdService.with_meta(access_token="...", ad_account_id="...")
        service = AdService(provider=meu_provider)
    """

    def __init__(
        self,
        provider: AdsProvider | None = None,
        provider_name: str = "mock",
        **provider_kwargs,
    ) -> None:
        self._provider = provider or get_ads_provider(provider_name, **provider_kwargs)

    # ── Construtores alternativos ──────────────────────────────────────────────

    @classmethod
    def with_mock(cls) -> "AdService":
        return cls(provider_name="mock")

    @classmethod
    def with_meta(cls, access_token: str, ad_account_id: str) -> "AdService":
        return cls(
            provider_name="meta",
            access_token=access_token,
            ad_account_id=ad_account_id,
        )

    # ── Campanhas ──────────────────────────────────────────────────────────────

    def create_campaign(self, data: dict) -> dict:
        result = self._provider.create_campaign(data)
        self._on_campaign_created(result)
        return result

    def update_campaign(self, campaign_id: str, data: dict) -> dict:
        return self._provider.update_campaign(campaign_id, data)

    def get_campaign(self, campaign_id: str) -> dict:
        return self._provider.get_campaign(campaign_id)

    def list_campaigns(self, filters: dict | None = None) -> list[dict]:
        return self._provider.list_campaigns(filters)

    def delete_campaign(self, campaign_id: str) -> dict:
        return self._provider.delete_campaign(campaign_id)

    def pause_campaign(self, campaign_id: str) -> dict:
        return self._provider.pause_campaign(campaign_id)

    def activate_campaign(self, campaign_id: str) -> dict:
        return self._provider.activate_campaign(campaign_id)

    # ── AdSets ─────────────────────────────────────────────────────────────────

    def create_adset(self, data: dict) -> dict:
        return self._provider.create_adset(data)

    # ── Ads ────────────────────────────────────────────────────────────────────

    def create_ad(self, data: dict) -> dict:
        return self._provider.create_ad(data)

    # ── Métricas ───────────────────────────────────────────────────────────────

    def get_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        return self._provider.get_metrics(campaign_id, period)

    # ── Conta ──────────────────────────────────────────────────────────────────

    def validate_account(self, account_id: str) -> bool:
        return self._provider.validate_account(account_id)

    # ── Publicação completa ────────────────────────────────────────────────────

    def publish_ad(self, data: dict) -> dict:
        """
        Fluxo completo de publicação:
        1. Gera copy via IA se solicitado e não fornecido
        2. Valida dados mínimos
        3. Orquestra campanha + adset + ad via AdsProvider
        4. Hook de persistência no banco (stub)

        data:
            generate_copy (bool)  — acionar geração de copy por IA
            campaign (dict)       — dados para create_campaign
            adset (dict)          — dados para create_adset
            ad (dict)             — dados para create_ad
        """
        self._maybe_generate_copy(data)
        result = self._provider.publish_ad(data)
        self._on_ad_published(result)
        return result

    # ── Hooks de extensão (sobrescreva em subclasses ou injeções) ──────────────

    def _maybe_generate_copy(self, data: dict) -> None:
        """Gera copy via IA caso solicitado e o campo esteja vazio."""
        if not data.get("generate_copy"):
            return
        ad_data = data.setdefault("ad", {})
        if not ad_data.get("copy"):
            ad_data["copy"] = self._generate_copy(data)
        if not ad_data.get("headline"):
            ad_data["headline"] = self._generate_headline(data)

    def _generate_copy(self, data: dict) -> str:
        """
        Stub de geração de copy.
        Substitua por chamada real à IA (ex: Claude API).
        """
        name = data.get("campaign", {}).get("name", "sua campanha")
        return f"Descubra como {name} pode transformar seus resultados. Clique e saiba mais!"

    def _generate_headline(self, data: dict) -> str:
        name = data.get("campaign", {}).get("name", "Truck Ads")
        return f"{name} — Resultados reais para o seu negócio"

    def _on_campaign_created(self, campaign: dict) -> None:
        """Hook: persistir campanha no banco. Implemente na subclasse ou injete."""

    def _on_ad_published(self, result: dict) -> None:
        """Hook: persistir resultado da publicação no banco. Implemente na subclasse."""

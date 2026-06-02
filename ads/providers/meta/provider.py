from __future__ import annotations

import os

from ads.provider import AdsProvider

from . import ads_ops, adsets, campaigns, creatives, metrics
from .client import MetaAPIClient

_PAGE_ID_ENV = "META_PAGE_ID"


class MetaAdsProvider(AdsProvider):
    """
    Meta Ads provider — Graph API v23.0.

    Required env vars:
        META_ACCESS_TOKEN   — System User Token with ads_management permission
        META_AD_ACCOUNT_ID  — Numeric ad account ID (without 'act_' prefix)
        META_PAGE_ID        — Facebook Page ID linked to the ad account
    """

    def __init__(
        self,
        access_token: str,
        ad_account_id: str,
        page_id: str = "",
        instagram_actor_id: str | None = None,
    ) -> None:
        self._client = MetaAPIClient(access_token=access_token, ad_account_id=ad_account_id)
        self._page_id: str = page_id or os.getenv(_PAGE_ID_ENV, "")
        self._instagram_actor_id = instagram_actor_id

    # ── Campanhas ──────────────────────────────────────────────────────────────

    def create_campaign(self, data: dict) -> dict:
        return campaigns.create_campaign(self._client, data)

    def update_campaign(self, campaign_id: str, data: dict) -> dict:
        return campaigns.update_campaign(self._client, campaign_id, data)

    def get_campaign(self, campaign_id: str) -> dict:
        return campaigns.get_campaign(self._client, campaign_id)

    def list_campaigns(self, filters: dict | None = None) -> list[dict]:
        return campaigns.list_campaigns(self._client, filters)

    def delete_campaign(self, campaign_id: str) -> dict:
        return campaigns.delete_campaign(self._client, campaign_id)

    # ── AdSets ─────────────────────────────────────────────────────────────────

    def create_adset(self, data: dict) -> dict:
        return adsets.create_adset(self._client, data)

    # ── Ads ────────────────────────────────────────────────────────────────────

    def create_ad(self, data: dict) -> dict:
        return ads_ops.create_ad(self._client, data, page_id=self._page_id)

    # ── Estado ─────────────────────────────────────────────────────────────────

    def pause_campaign(self, campaign_id: str) -> dict:
        return self.update_campaign(campaign_id, {"status": "PAUSED"})

    def activate_campaign(self, campaign_id: str) -> dict:
        return self.update_campaign(campaign_id, {"status": "ACTIVE"})

    def update_ad_status(self, ad_id: str, status: str) -> dict:
        """Update a single ad's status via PATCH /{ad_id} on the Meta Graph API."""
        return self._client.patch(ad_id, {"status": status})

    def activate_ad(self, ad_id: str) -> dict:
        return self.update_ad_status(ad_id, "ACTIVE")

    def pause_ad(self, ad_id: str) -> dict:
        return self.update_ad_status(ad_id, "PAUSED")

    # ── Métricas ───────────────────────────────────────────────────────────────

    def get_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        return metrics.get_campaign_insights(self._client, campaign_id, period)

    def get_campaign_insights(self, campaign_id: str, period: str = "last_7d") -> dict:
        return metrics.get_campaign_insights(self._client, campaign_id, period)

    # ── Conta ──────────────────────────────────────────────────────────────────

    def validate_account(self, account_id: str) -> bool:
        return self._client.validate_connection()

    # ── Publicação orquestrada ─────────────────────────────────────────────────

    def publish_ad(self, data: dict) -> dict:
        campaign = self.create_campaign(data.get("campaign", {}))

        adset_data = {**data.get("adset", {}), "campaign_id": campaign["id"]}
        adset = self.create_adset(adset_data)

        ad_data = {
            **data.get("ad", {}),
            "campaign_id": campaign["id"],
            "adset_id": adset["id"],
        }
        ad = self.create_ad(ad_data)

        return {
            "success": True,
            "message": "Ad published to Meta Ads",
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
        }

    # ── Upload de imagem ───────────────────────────────────────────────────────

    def upload_image(self, image_bytes: bytes, filename: str = "image.jpg") -> str:
        """Upload image to Meta ad account and return its image_hash."""
        return creatives.upload_image(self._client, image_bytes, filename)

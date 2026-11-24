from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

_now = lambda: datetime.now(timezone.utc)

from ..exceptions import (
    AdSetNotFound,
    AdsError,
    CampaignNotFound,
    CreationError,
    InvalidAccount,
    InvalidTransition,
)
from ..models import Ad, AdSet, Audience, Campaign, CampaignStatus, Creative, Metrics
from ..provider import AdsProvider

# Contas reconhecidas pelo mock — qualquer outra levanta InvalidAccount
_VALID_ACCOUNTS: frozenset[str] = frozenset(
    {"mock_account_001", "mock_account_002", "truck_ads_demo"}
)

# Transições de estado permitidas
_VALID_TRANSITIONS: dict[CampaignStatus, set[CampaignStatus]] = {
    CampaignStatus.DRAFT: {CampaignStatus.ACTIVE},
    CampaignStatus.ACTIVE: {CampaignStatus.PAUSED},
    CampaignStatus.PAUSED: {CampaignStatus.ACTIVE},
}


class MockAdsProvider(AdsProvider):
    """
    Implementação in-memory do AdsProvider para desenvolvimento e testes.
    Simula persistência, métricas aleatórias coerentes e validação de estados.
    """

    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}
        self._adsets: dict[str, AdSet] = {}
        self._ads: dict[str, Ad] = {}

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _gen_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}"

    def _get_campaign_or_raise(self, campaign_id: str) -> Campaign:
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _get_adset_or_raise(self, adset_id: str) -> AdSet:
        adset = self._adsets.get(adset_id)
        if not adset:
            raise AdSetNotFound(adset_id)
        return adset

    def _transition(self, campaign: Campaign, target: CampaignStatus) -> None:
        current = (
            campaign.status
            if isinstance(campaign.status, CampaignStatus)
            else CampaignStatus(campaign.status)
        )
        if target not in _VALID_TRANSITIONS.get(current, set()):
            raise InvalidTransition(current.value, target.value)
        campaign.status = target
        campaign.updated_at = _now()

    # ── Campanhas ──────────────────────────────────────────────────────────────

    def create_campaign(self, data: dict) -> dict:
        if not data.get("name"):
            raise CreationError("campaign", "field 'name' is required")
        if not data.get("objective"):
            raise CreationError("campaign", "field 'objective' is required")

        campaign = Campaign(
            id=self._gen_id("cmp"),
            name=data["name"],
            objective=data["objective"],
            status=CampaignStatus.DRAFT,
            budget=float(data.get("budget", 0.0)),
            created_at=_now(),
            extra=dict(data.get("extra") or {}),
        )
        self._campaigns[campaign.id] = campaign
        return campaign.to_dict()

    def update_campaign(self, campaign_id: str, data: dict) -> dict:
        campaign = self._get_campaign_or_raise(campaign_id)
        if "name" in data:
            campaign.name = data["name"]
        if "budget" in data:
            campaign.budget = float(data["budget"])
        if "objective" in data:
            campaign.objective = data["objective"]
        campaign.updated_at = _now()
        return campaign.to_dict()

    def get_campaign(self, campaign_id: str) -> dict:
        return self._get_campaign_or_raise(campaign_id).to_dict()

    def list_campaigns(self, filters: dict | None = None) -> list[dict]:
        results = list(self._campaigns.values())
        if filters:
            if status := filters.get("status"):
                results = [c for c in results if c.status.value == status]
            if fragment := filters.get("name_contains"):
                results = [c for c in results if fragment.lower() in c.name.lower()]
        return [c.to_dict() for c in results]

    def delete_campaign(self, campaign_id: str) -> dict:
        self._get_campaign_or_raise(campaign_id)

        # Cascata: remove adsets e ads associados
        for adset_id in [k for k, v in self._adsets.items() if v.campaign_id == campaign_id]:
            del self._adsets[adset_id]
        for ad_id in [k for k, v in self._ads.items() if v.campaign_id == campaign_id]:
            del self._ads[ad_id]

        del self._campaigns[campaign_id]
        return {"deleted": True, "campaign_id": campaign_id}

    # ── AdSets ─────────────────────────────────────────────────────────────────

    def create_adset(self, data: dict) -> dict:
        campaign_id = data.get("campaign_id", "")
        if campaign_id not in self._campaigns:
            raise CreationError("adset", f"campaign_id '{campaign_id}' not found")

        adset = AdSet(
            id=self._gen_id("ads"),
            campaign_id=campaign_id,
            name=data.get("name") or f"AdSet {self._gen_id('n')}",
            audience=Audience.from_dict(data.get("audience", {})),
            budget=float(data.get("budget", 0.0)),
            schedule=data.get("schedule", {}),
            created_at=_now(),
        )
        self._adsets[adset.id] = adset
        return adset.to_dict()

    # ── Ads ────────────────────────────────────────────────────────────────────

    def create_ad(self, data: dict) -> dict:
        campaign_id = data.get("campaign_id", "")
        adset_id = data.get("adset_id", "")

        if campaign_id not in self._campaigns:
            raise CreationError("ad", f"campaign_id '{campaign_id}' not found")
        if adset_id not in self._adsets:
            raise CreationError("ad", f"adset_id '{adset_id}' not found")

        ad = Ad(
            id=self._gen_id("ad"),
            campaign_id=campaign_id,
            adset_id=adset_id,
            name=data.get("name") or f"Ad {self._gen_id('n')}",
            copy=data.get("copy", ""),
            headline=data.get("headline", ""),
            creative=Creative.from_dict(data.get("creative", {})),
            destination=data.get("destination", ""),
            created_at=_now(),
        )
        self._ads[ad.id] = ad
        return ad.to_dict()

    # ── Controle de estado ─────────────────────────────────────────────────────

    def pause_campaign(self, campaign_id: str) -> dict:
        campaign = self._get_campaign_or_raise(campaign_id)
        self._transition(campaign, CampaignStatus.PAUSED)
        return campaign.to_dict()

    def activate_campaign(self, campaign_id: str) -> dict:
        campaign = self._get_campaign_or_raise(campaign_id)
        self._transition(campaign, CampaignStatus.ACTIVE)
        return campaign.to_dict()

    # ── Conta ──────────────────────────────────────────────────────────────────

    def validate_account(self, account_id: str) -> bool:
        if account_id not in _VALID_ACCOUNTS:
            raise InvalidAccount(account_id)
        return True

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
            "message": "Ad published successfully (mock)",
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
        }

    # ── Estado interno (útil em testes) ───────────────────────────────────────

    def snapshot(self) -> dict:
        """Retorna uma cópia do estado completo do mock — útil em testes."""
        return {
            "campaigns": {k: v.to_dict() for k, v in self._campaigns.items()},
            "adsets": {k: v.to_dict() for k, v in self._adsets.items()},
            "ads": {k: v.to_dict() for k, v in self._ads.items()},
        }

    def reset(self) -> None:
        """Limpa todo o estado — útil para isolar testes."""
        self._campaigns.clear()
        self._adsets.clear()
        self._ads.clear()

    # ── Demo data ──────────────────────────────────────────────────────────────

    @classmethod
    def with_demo_data(cls) -> "MockAdsProvider":
        """
        Retorna uma instância pré-carregada com campanhas de caminhões de exemplo.
        Após passarem pelo adapter (to_frontend_dto), resultam no padrão JSON
        exato que renderCampanhas() do frontend consome.
        """
        instance = cls()
        instance._seed_truck_campaigns()
        return instance

    def _seed_truck_campaigns(self) -> None:
        from datetime import timedelta

        seed: list[dict] = [
            {
                "modelo": "Volvo FH 540",
                "cor": "Branco",
                "ano": "2023",
                "preco": "R$ 380.000",
                "km": "120.000 km",
                "cidade": "Curitiba",
                "estado": "PR",
                "status": CampaignStatus.ACTIVE,
                "budget": 150.0,
                "days_ago": 5,
                "leads": 12,
                "spent": 150.50,
            },
            {
                "modelo": "Scania R 450",
                "cor": "Cinza",
                "ano": "2022",
                "preco": "R$ 320.000",
                "km": "200.000 km",
                "cidade": "São Paulo",
                "estado": "SP",
                "status": CampaignStatus.PAUSED,
                "budget": 100.0,
                "days_ago": 12,
                "leads": 7,
                "spent": 98.20,
            },
            {
                "modelo": "Mercedes Actros 2651",
                "cor": "Vermelho",
                "ano": "2021",
                "preco": "R$ 290.000",
                "km": "350.000 km",
                "cidade": "Porto Alegre",
                "estado": "RS",
                "status": CampaignStatus.DRAFT,
                "budget": 80.0,
                "days_ago": 1,
                "leads": 0,
                "spent": 0.0,
            },
        ]

        for s in seed:
            created_at = _now() - timedelta(days=s["days_ago"])
            campaign = Campaign(
                id=self._gen_id("cmp"),
                name=f"{s['modelo']} {s['ano']} — {s['cidade']}, {s['estado']}",
                objective="OUTCOME_LEADS",
                status=s["status"],
                budget=s["budget"],
                created_at=created_at,
                extra={
                    "modelo": s["modelo"],
                    "cor": s["cor"],
                    "ano": s["ano"],
                    "preco": s["preco"],
                    "km": s["km"],
                    "cidade": s["cidade"],
                    "estado": s["estado"],
                    # Store fixed metrics for consistent demo output
                    "_demo_leads": s["leads"],
                    "_demo_spent": s["spent"],
                },
            )
            self._campaigns[campaign.id] = campaign

    def get_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        campaign = self._get_campaign_or_raise(campaign_id)

        # Use fixed demo metrics if seeded; otherwise generate random ones
        extra = campaign.extra or {}
        if "_demo_leads" in extra:
            leads = extra["_demo_leads"]
            spent = extra["_demo_spent"]
            impressions = leads * random.randint(800, 1200)
            clicks = leads * random.randint(5, 15)
            cpl = round(spent / leads, 2) if leads else 0.0
        else:
            impressions = random.randint(2_000, 80_000)
            clicks = random.randint(80, max(81, impressions // 8))
            leads = random.randint(1, max(2, clicks // 6))
            spent = round(random.uniform(50.0, 800.0), 2)
            cpl = round(spent / leads, 2) if leads else 0.0

        return Metrics(
            campaign_id=campaign_id,
            impressions=impressions,
            clicks=clicks,
            leads=leads,
            spent=spent,
            cpl=cpl,
            period=period,
        ).to_dict()

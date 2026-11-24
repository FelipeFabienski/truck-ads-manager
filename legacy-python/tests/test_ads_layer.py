"""
Testes da camada de abstração de anúncios — Truck Ads Manager.
Execute com: python -m pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ads import (
    AdService,
    AdsError,
    CampaignNotFound,
    CampaignStatus,
    CreationError,
    InvalidAccount,
    InvalidTransition,
    clear_registry,
    get_ads_provider,
)
from ads.providers import MockAdsProvider


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def provider():
    return MockAdsProvider()


@pytest.fixture
def service():
    return AdService.with_mock()


@pytest.fixture
def campaign_data():
    return {
        "name": "Campanha Frete SP",
        "objective": "OUTCOME_LEADS",
        "budget": 150.0,
    }


@pytest.fixture
def created_campaign(provider, campaign_data):
    return provider.create_campaign(campaign_data)


# ── Factory ────────────────────────────────────────────────────────────────────

class TestFactory:
    def test_returns_mock_by_default(self):
        p = get_ads_provider()
        assert isinstance(p, MockAdsProvider)

    def test_returns_same_instance_on_second_call(self):
        p1 = get_ads_provider("mock")
        p2 = get_ads_provider("mock")
        assert p1 is p2

    def test_raises_on_unknown_provider(self):
        with pytest.raises(AdsError) as exc_info:
            get_ads_provider("google")
        assert exc_info.value.code == "UNKNOWN_PROVIDER"

    def test_raises_meta_without_credentials(self):
        with pytest.raises(AdsError) as exc_info:
            get_ads_provider("meta")
        assert exc_info.value.code == "MISSING_META_CONFIG"


# ── Campanhas ──────────────────────────────────────────────────────────────────

class TestCampaigns:
    def test_create_returns_draft(self, provider, campaign_data):
        result = provider.create_campaign(campaign_data)
        assert result["status"] == CampaignStatus.DRAFT.value
        assert result["name"] == campaign_data["name"]
        assert result["id"].startswith("cmp_")

    def test_create_requires_name(self, provider):
        with pytest.raises(CreationError):
            provider.create_campaign({"objective": "OUTCOME_LEADS"})

    def test_create_requires_objective(self, provider):
        with pytest.raises(CreationError):
            provider.create_campaign({"name": "Sem objetivo"})

    def test_get_existing_campaign(self, provider, created_campaign):
        result = provider.get_campaign(created_campaign["id"])
        assert result["id"] == created_campaign["id"]

    def test_get_nonexistent_raises(self, provider):
        with pytest.raises(CampaignNotFound):
            provider.get_campaign("cmp_does_not_exist")

    def test_update_campaign(self, provider, created_campaign):
        updated = provider.update_campaign(created_campaign["id"], {"name": "Novo Nome"})
        assert updated["name"] == "Novo Nome"
        assert updated["updated_at"] is not None

    def test_list_campaigns(self, provider, campaign_data):
        provider.create_campaign(campaign_data)
        provider.create_campaign({**campaign_data, "name": "Outra Campanha"})
        results = provider.list_campaigns()
        assert len(results) == 2

    def test_list_campaigns_filter_by_status(self, provider, campaign_data):
        c = provider.create_campaign(campaign_data)
        provider.activate_campaign(c["id"])
        provider.create_campaign({**campaign_data, "name": "Draft"})

        active = provider.list_campaigns({"status": "active"})
        assert len(active) == 1
        assert active[0]["status"] == "active"

    def test_list_campaigns_filter_by_name(self, provider, campaign_data):
        provider.create_campaign(campaign_data)
        provider.create_campaign({**campaign_data, "name": "Logística Norte"})

        results = provider.list_campaigns({"name_contains": "frete"})
        assert len(results) == 1

    def test_delete_campaign(self, provider, created_campaign):
        result = provider.delete_campaign(created_campaign["id"])
        assert result["deleted"] is True
        with pytest.raises(CampaignNotFound):
            provider.get_campaign(created_campaign["id"])

    def test_delete_nonexistent_raises(self, provider):
        with pytest.raises(CampaignNotFound):
            provider.delete_campaign("cmp_ghost")


# ── Transições de estado ───────────────────────────────────────────────────────

class TestStatusTransitions:
    def test_draft_to_active(self, provider, created_campaign):
        result = provider.activate_campaign(created_campaign["id"])
        assert result["status"] == "active"

    def test_active_to_paused(self, provider, created_campaign):
        provider.activate_campaign(created_campaign["id"])
        result = provider.pause_campaign(created_campaign["id"])
        assert result["status"] == "paused"

    def test_paused_to_active(self, provider, created_campaign):
        provider.activate_campaign(created_campaign["id"])
        provider.pause_campaign(created_campaign["id"])
        result = provider.activate_campaign(created_campaign["id"])
        assert result["status"] == "active"

    def test_draft_to_paused_invalid(self, provider, created_campaign):
        with pytest.raises(InvalidTransition):
            provider.pause_campaign(created_campaign["id"])

    def test_active_to_draft_invalid(self, provider, created_campaign):
        provider.activate_campaign(created_campaign["id"])
        with pytest.raises(InvalidTransition):
            # draft não está em VALID_TRANSITIONS[ACTIVE]
            from ads.models import CampaignStatus as CS
            from ads.exceptions import InvalidTransition as IT
            provider._transition(
                provider._campaigns[created_campaign["id"]], CS.DRAFT
            )


# ── AdSets ─────────────────────────────────────────────────────────────────────

class TestAdSets:
    def test_create_adset(self, provider, created_campaign):
        adset = provider.create_adset({
            "campaign_id": created_campaign["id"],
            "name": "Público SP 25-45",
            "audience": {
                "locations": ["BR"],
                "age_min": 25,
                "age_max": 45,
                "interests": ["Logística", "Transporte"],
            },
            "budget": 75.0,
            "schedule": {"start_time": "2026-06-01T00:00:00"},
        })
        assert adset["id"].startswith("ads_")
        assert adset["campaign_id"] == created_campaign["id"]
        assert adset["audience"]["age_min"] == 25

    def test_create_adset_invalid_campaign(self, provider):
        with pytest.raises(CreationError):
            provider.create_adset({"campaign_id": "cmp_ghost"})


# ── Ads ────────────────────────────────────────────────────────────────────────

class TestAds:
    def test_create_ad(self, provider, created_campaign):
        adset = provider.create_adset({"campaign_id": created_campaign["id"], "budget": 50})
        ad = provider.create_ad({
            "campaign_id": created_campaign["id"],
            "adset_id": adset["id"],
            "name": "Anúncio Principal",
            "copy": "Frete rápido e seguro para todo o Brasil.",
            "headline": "Seu caminhão, nossa plataforma",
            "creative": {"type": "image", "url": "https://cdn.example.com/banner.jpg"},
            "destination": "https://wa.me/5511999990000",
        })
        assert ad["id"].startswith("ad_")
        assert ad["copy"] == "Frete rápido e seguro para todo o Brasil."

    def test_create_ad_invalid_adset(self, provider, created_campaign):
        with pytest.raises(CreationError):
            provider.create_ad({
                "campaign_id": created_campaign["id"],
                "adset_id": "ads_ghost",
            })


# ── Métricas ───────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_get_metrics_returns_valid_structure(self, provider, created_campaign):
        metrics = provider.get_metrics(created_campaign["id"])
        assert metrics["campaign_id"] == created_campaign["id"]
        assert metrics["impressions"] > 0
        assert metrics["clicks"] >= 0
        assert metrics["spent"] > 0
        assert "cpl" in metrics

    def test_get_metrics_nonexistent_raises(self, provider):
        with pytest.raises(CampaignNotFound):
            provider.get_metrics("cmp_ghost")


# ── Validação de conta ─────────────────────────────────────────────────────────

class TestAccountValidation:
    def test_valid_account(self, provider):
        assert provider.validate_account("mock_account_001") is True

    def test_invalid_account(self, provider):
        with pytest.raises(InvalidAccount):
            provider.validate_account("conta_invalida_xyz")


# ── Publicação orquestrada ─────────────────────────────────────────────────────

class TestPublishAd:
    def test_publish_creates_all_entities(self, provider):
        result = provider.publish_ad({
            "campaign": {"name": "Campanha Completa", "objective": "OUTCOME_LEADS", "budget": 200},
            "adset": {"name": "Conjunto 1", "budget": 100, "audience": {"locations": ["BR"]}},
            "ad": {
                "name": "Anúncio 1",
                "copy": "Texto do anúncio",
                "headline": "Título do anúncio",
                "destination": "https://wa.me/5511999990000",
            },
        })
        assert result["success"] is True
        assert result["campaign"]["id"] is not None
        assert result["adset"]["campaign_id"] == result["campaign"]["id"]
        assert result["ad"]["adset_id"] == result["adset"]["id"]


# ── AdService ──────────────────────────────────────────────────────────────────

class TestAdService:
    def test_service_delegates_to_provider(self, service, campaign_data):
        result = service.create_campaign(campaign_data)
        assert result["status"] == "draft"

    def test_generate_copy_on_publish(self):
        service = AdService.with_mock()
        result = service.publish_ad({
            "generate_copy": True,
            "campaign": {"name": "Truck Ads Nordeste", "objective": "OUTCOME_LEADS"},
            "adset": {"budget": 50},
            "ad": {"destination": "https://wa.me/5511111111111"},
        })
        assert result["success"] is True
        assert len(result["ad"]["copy"]) > 0

    def test_snapshot_reflects_state(self):
        provider = MockAdsProvider()
        provider.create_campaign({"name": "A", "objective": "OUTCOME_LEADS"})
        snapshot = provider.snapshot()
        assert len(snapshot["campaigns"]) == 1

    def test_reset_clears_state(self):
        provider = MockAdsProvider()
        provider.create_campaign({"name": "A", "objective": "OUTCOME_LEADS"})
        provider.reset()
        assert provider.list_campaigns() == []

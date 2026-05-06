"""
Testes da camada de domínio Truck Ads — Truck Ads Manager.
Execute com: python -m pytest tests/test_truck_layer.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pydantic import ValidationError

from ads.providers.mock_provider import MockAdsProvider
from ads.truck.adapter import (
    _parse_created,
    to_frontend_dto,
    translate_status_to_en,
    translate_status_to_pt,
)
from ads.truck.ai_generator import MockAIGenerator
from ads.truck.schemas import TruckAdCreateRequest
from ads.truck.service import TruckAdService


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_request() -> TruckAdCreateRequest:
    return TruckAdCreateRequest(
        modelo="Volvo FH 540",
        cor="Branco",
        ano="2023",
        preco="R$ 380.000",
        km="120.000 km",
        budget=150.0,
        duracao=30,
        vendedor_nome="Carlos Silva",
        vendedor_wpp="41999990000",
        cidade="Curitiba",
        estado="PR",
        publico_idade_min=25,
        publico_idade_max=55,
        publico_raio=80,
        publico_genero="male",
        publico_interesses="Logística, Transporte, Caminhões",
        publico_posicionamentos=["feed", "stories"],
    )


@pytest.fixture
def service() -> TruckAdService:
    # Bypass the factory cache: each test gets its own isolated MockAdsProvider
    return TruckAdService(provider=MockAdsProvider())


# ── TruckAdCreateRequest (Pydantic validation) ─────────────────────────────────

class TestTruckAdCreateRequest:
    def test_valid_request_parses_correctly(self, valid_request):
        assert valid_request.modelo == "Volvo FH 540"
        assert valid_request.estado == "PR"  # uppercase enforced
        assert valid_request.vendedor_wpp == "41999990000"

    def test_estado_is_uppercased(self):
        req = TruckAdCreateRequest(
            modelo="Scania", cor="Cinza", ano="2022",
            budget=100, vendedor_nome="João", vendedor_wpp="11988880000",
            cidade="SP", estado="sp",
        )
        assert req.estado == "SP"

    def test_invalid_ano_format(self):
        with pytest.raises(ValidationError, match="pattern"):
            TruckAdCreateRequest(
                modelo="Scania", cor="Cinza", ano="22",
                budget=100, vendedor_nome="João", vendedor_wpp="11988880000",
                cidade="SP", estado="SP",
            )

    def test_budget_must_be_positive(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            TruckAdCreateRequest(
                modelo="Scania", cor="Cinza", ano="2022",
                budget=0, vendedor_nome="João", vendedor_wpp="11988880000",
                cidade="SP", estado="SP",
            )

    def test_idade_range_invalid(self):
        with pytest.raises(ValidationError, match="publico_idade_min must be less"):
            TruckAdCreateRequest(
                modelo="Scania", cor="Cinza", ano="2022",
                budget=100, vendedor_nome="João", vendedor_wpp="11988880000",
                cidade="SP", estado="SP",
                publico_idade_min=50,
                publico_idade_max=30,
            )

    def test_genero_invalid(self):
        with pytest.raises(ValidationError, match="publico_genero must be one of"):
            TruckAdCreateRequest(
                modelo="Scania", cor="Cinza", ano="2022",
                budget=100, vendedor_nome="João", vendedor_wpp="11988880000",
                cidade="SP", estado="SP",
                publico_genero="unknown",
            )

    def test_wpp_strips_to_digits(self):
        req = TruckAdCreateRequest(
            modelo="Scania", cor="Cinza", ano="2022",
            budget=100, vendedor_nome="João", vendedor_wpp="+55 (41) 9 9999-0000",
            cidade="SP", estado="SP",
        )
        assert req.vendedor_wpp.isdigit()

    def test_wpp_too_short_raises(self):
        with pytest.raises(ValidationError, match="at least 10 digits"):
            TruckAdCreateRequest(
                modelo="Scania", cor="Cinza", ano="2022",
                budget=100, vendedor_nome="João", vendedor_wpp="123",
                cidade="SP", estado="SP",
            )

    def test_optional_fields_default_to_none(self):
        req = TruckAdCreateRequest(
            modelo="Scania", cor="Cinza", ano="2022",
            budget=100, vendedor_nome="João", vendedor_wpp="11988880000",
            cidade="SP", estado="SP",
        )
        assert req.preco is None
        assert req.km is None

    def test_duracao_zero_is_continuous(self):
        req = TruckAdCreateRequest(
            modelo="Scania", cor="Cinza", ano="2022",
            budget=100, vendedor_nome="João", vendedor_wpp="11988880000",
            cidade="SP", estado="SP",
            duracao=0,
        )
        assert req.duracao == 0


# ── MockAIGenerator ────────────────────────────────────────────────────────────

class TestMockAIGenerator:
    def test_generate_returns_all_fields(self, valid_request):
        content = MockAIGenerator().generate(valid_request)
        assert content.ad_copy
        assert content.headline
        assert content.roteiro

    def test_copy_mentions_modelo(self, valid_request):
        content = MockAIGenerator().generate(valid_request)
        assert "Volvo FH 540" in content.ad_copy

    def test_roteiro_contains_wpp_link(self, valid_request):
        content = MockAIGenerator().generate(valid_request)
        assert valid_request.vendedor_wpp in content.roteiro

    def test_headline_contains_location(self, valid_request):
        content = MockAIGenerator().generate(valid_request)
        assert "Curitiba" in content.headline or "PR" in content.headline


# ── Adapter ────────────────────────────────────────────────────────────────────

class TestAdapter:
    def test_translate_status_to_pt(self):
        assert translate_status_to_pt("draft") == "rascunho"
        assert translate_status_to_pt("active") == "ativo"
        assert translate_status_to_pt("paused") == "pausado"
        assert translate_status_to_pt("deleted") == "removido"

    def test_translate_status_to_en(self):
        assert translate_status_to_en("rascunho") == "draft"
        assert translate_status_to_en("ativo") == "active"
        assert translate_status_to_en("pausado") == "paused"

    def test_translate_unknown_passthrough(self):
        assert translate_status_to_pt("unknown_status") == "unknown_status"

    def test_to_frontend_dto_full(self):
        campaign = {
            "id": "cmp_abc123",
            "name": "Volvo FH 540 2023 — Curitiba, PR",
            "status": "active",
            "budget": 150.0,
            "created_at": "2026-05-05T10:00:00+00:00",
            "extra": {
                "modelo": "Volvo FH 540",
                "cor": "Branco",
                "ano": "2023",
                "preco": "R$ 380.000",
                "km": "120.000 km",
                "cidade": "Curitiba",
                "estado": "PR",
            },
        }
        metrics = {"leads": 12, "spent": 150.50}
        result = to_frontend_dto(campaign, metrics)

        assert result["campaign_id"] == "cmp_abc123"
        assert isinstance(result["id"], int)
        assert result["modelo"] == "Volvo FH 540"
        assert result["cor"] == "Branco"
        assert result["ano"] == "2023"
        assert result["cidade"] == "Curitiba, PR"
        assert result["preco"] == "R$ 380.000"
        assert result["km"] == "120.000 km"
        assert result["status"] == "ativo"
        assert result["leads"] == 12
        assert result["spend"] == 150.50
        assert result["created"] == "05/05/2026"

    def test_to_frontend_dto_without_metrics(self):
        campaign = {
            "id": "cmp_x",
            "status": "draft",
            "created_at": "2026-05-05T00:00:00+00:00",
            "extra": {},
        }
        result = to_frontend_dto(campaign)
        assert result["leads"] == 0
        assert result["spend"] == 0.0
        assert result["status"] == "rascunho"

    def test_to_frontend_dto_without_extra(self):
        campaign = {
            "id": "cmp_y",
            "name": "Fallback Name",
            "status": "paused",
            "created_at": "2026-05-05T00:00:00+00:00",
        }
        result = to_frontend_dto(campaign)
        assert result["modelo"] == "Fallback Name"
        assert result["status"] == "pausado"
        assert result["cor"] == ""

    def test_id_is_timestamp_ms(self):
        campaign = {"id": "x", "status": "draft", "created_at": "2026-05-05T10:00:00+00:00"}
        result = to_frontend_dto(campaign)
        # Should be ~13 digits (ms timestamp)
        assert len(str(result["id"])) == 13

    def test_parse_created_fallback_on_bad_date(self):
        frontend_id, created_str = _parse_created("not-a-date")
        # Must not raise — should return fallback values
        assert isinstance(frontend_id, int)
        assert "/" in created_str


# ── TruckAdService ─────────────────────────────────────────────────────────────

class TestTruckAdService:
    def test_create_and_publish_returns_response(self, service, valid_request):
        response = service.create_and_publish_truck_ad(valid_request)
        assert response.status == "rascunho"
        assert response.modelo == "Volvo FH 540"
        assert response.cor == "Branco"
        assert response.ano == "2023"
        assert response.campaign_id.startswith("cmp_")
        assert isinstance(response.id, int)

    def test_response_contains_ai_copy(self, service, valid_request):
        response = service.create_and_publish_truck_ad(valid_request)
        assert len(response.ad_copy) > 0
        assert len(response.headline) > 0
        assert len(response.roteiro) > 0

    def test_response_cidade_concatenated(self, service, valid_request):
        response = service.create_and_publish_truck_ad(valid_request)
        assert response.cidade == "Curitiba, PR"

    def test_response_preco_and_km_preserved(self, service, valid_request):
        response = service.create_and_publish_truck_ad(valid_request)
        assert response.preco == "R$ 380.000"
        assert response.km == "120.000 km"

    def test_response_optional_fields_empty_when_not_provided(self, service):
        req = TruckAdCreateRequest(
            modelo="Scania R 450", cor="Cinza", ano="2022",
            budget=100.0, duracao=0,
            vendedor_nome="Pedro", vendedor_wpp="11988880000",
            cidade="São Paulo", estado="SP",
        )
        response = service.create_and_publish_truck_ad(req)
        assert response.preco == ""
        assert response.km == ""

    def test_schedule_empty_for_continuous(self, service):
        req = TruckAdCreateRequest(
            modelo="Scania", cor="Cinza", ano="2022",
            budget=100, duracao=0,
            vendedor_nome="Pedro", vendedor_wpp="11988880000",
            cidade="SP", estado="SP",
        )
        # Internal mapping should produce empty schedule
        payload = service._map_to_provider_payload(req, MockAIGenerator().generate(req))
        assert payload["adset"]["schedule"] == {}

    def test_schedule_has_end_time_when_duracao_set(self, service, valid_request):
        payload = service._map_to_provider_payload(
            valid_request, MockAIGenerator().generate(valid_request)
        )
        assert "end_time" in payload["adset"]["schedule"]

    def test_interests_parsed_from_csv(self, service, valid_request):
        payload = service._map_to_provider_payload(
            valid_request, MockAIGenerator().generate(valid_request)
        )
        interests = payload["adset"]["audience"]["interests"]
        assert "Logística" in interests
        assert "Transporte" in interests

    def test_destination_is_wpp_url(self, service, valid_request):
        payload = service._map_to_provider_payload(
            valid_request, MockAIGenerator().generate(valid_request)
        )
        assert payload["ad"]["destination"] == "https://wa.me/41999990000"

    def test_extra_stored_in_provider(self, service, valid_request):
        response = service.create_and_publish_truck_ad(valid_request)
        # The provider should have the campaign with extra data
        raw = service._provider.get_campaign(response.campaign_id)
        assert raw["extra"]["modelo"] == "Volvo FH 540"
        assert raw["extra"]["cidade"] == "Curitiba"
        assert raw["extra"]["estado"] == "PR"

    def test_list_campaigns_for_frontend_empty(self, service):
        result = service.list_campaigns_for_frontend()
        assert result == []

    def test_list_campaigns_for_frontend_after_publish(self, service, valid_request):
        service.create_and_publish_truck_ad(valid_request)
        result = service.list_campaigns_for_frontend()
        assert len(result) == 1
        row = result[0]
        assert row["modelo"] == "Volvo FH 540"
        assert row["status"] == "rascunho"
        assert isinstance(row["id"], int)
        assert row["cidade"] == "Curitiba, PR"

    def test_list_campaigns_frontend_has_metrics(self, service, valid_request):
        service.create_and_publish_truck_ad(valid_request)
        result = service.list_campaigns_for_frontend()
        row = result[0]
        assert "leads" in row
        assert "spend" in row


# ── MockAdsProvider com demo data ──────────────────────────────────────────────

class TestMockWithDemoData:
    def test_with_demo_data_has_three_campaigns(self):
        provider = MockAdsProvider.with_demo_data()
        campaigns = provider.list_campaigns()
        assert len(campaigns) == 3

    def test_demo_campaigns_have_extra_metadata(self):
        provider = MockAdsProvider.with_demo_data()
        for c in provider.list_campaigns():
            assert c["extra"]["modelo"] != ""
            assert c["extra"]["cidade"] != ""

    def test_demo_data_via_service_matches_frontend_contract(self):
        provider = MockAdsProvider.with_demo_data()
        service = TruckAdService(provider=provider)
        result = service.list_campaigns_for_frontend()
        assert len(result) == 3

        # Verify the Volvo FH 540 entry matches the expected frontend contract
        volvo = next(r for r in result if r["modelo"] == "Volvo FH 540")
        assert volvo["cor"] == "Branco"
        assert volvo["ano"] == "2023"
        assert volvo["cidade"] == "Curitiba, PR"
        assert volvo["preco"] == "R$ 380.000"
        assert volvo["km"] == "120.000 km"
        assert volvo["status"] == "ativo"
        assert volvo["leads"] == 12
        assert volvo["spend"] == 150.50
        assert "/" in volvo["created"]

    def test_demo_status_translation(self):
        provider = MockAdsProvider.with_demo_data()
        service = TruckAdService(provider=provider)
        result = service.list_campaigns_for_frontend()

        statuses = {r["modelo"]: r["status"] for r in result}
        assert statuses["Volvo FH 540"] == "ativo"
        assert statuses["Scania R 450"] == "pausado"
        assert statuses["Mercedes Actros 2651"] == "rascunho"

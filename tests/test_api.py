"""
Testes dos endpoints FastAPI — Truck Ads Manager.
Execute com: python -m pytest tests/test_api.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from ads.providers.mock_provider import MockAdsProvider
from ads.truck.service import TruckAdService
from api.dependencies import get_truck_service
from api.main import create_app


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def service() -> TruckAdService:
    return TruckAdService(provider=MockAdsProvider())


@pytest.fixture
def client(service: TruckAdService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_truck_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def demo_client() -> TestClient:
    """Client pré-carregado com dados de demonstração."""
    provider = MockAdsProvider.with_demo_data()
    demo_service = TruckAdService(provider=provider)
    app = create_app()
    app.dependency_overrides[get_truck_service] = lambda: demo_service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_payload() -> dict:
    return {
        "modelo": "Volvo FH 540",
        "cor": "Branco",
        "ano": "2023",
        "preco": "R$ 380.000",
        "km": "120.000 km",
        "budget": 150.0,
        "duracao": 30,
        "vendedor_nome": "Carlos Silva",
        "vendedor_wpp": "41999990000",
        "cidade": "Curitiba",
        "estado": "PR",
        "publico_idade_min": 25,
        "publico_idade_max": 55,
        "publico_raio": 80,
        "publico_genero": "male",
        "publico_interesses": "Logística, Transporte",
        "publico_posicionamentos": ["feed", "stories"],
    }


# ── GET /health ────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert "provider" in body


# ── POST /ads/truck ────────────────────────────────────────────────────────────

class TestPublishTruckAd:
    def test_returns_201(self, client, valid_payload):
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 201

    def test_response_has_required_fields(self, client, valid_payload):
        body = client.post("/ads/truck/", json=valid_payload).json()
        for field in ("id", "campaign_id", "status", "modelo", "cor", "ano",
                      "cidade", "copy", "headline", "roteiro", "budget", "created"):
            assert field in body, f"Missing field: {field}"

    def test_status_is_rascunho(self, client, valid_payload):
        body = client.post("/ads/truck/", json=valid_payload).json()
        assert body["status"] == "rascunho"

    def test_id_is_timestamp_ms(self, client, valid_payload):
        body = client.post("/ads/truck/", json=valid_payload).json()
        assert len(str(body["id"])) == 13

    def test_cidade_concatenated(self, client, valid_payload):
        body = client.post("/ads/truck/", json=valid_payload).json()
        assert body["cidade"] == "Curitiba, PR"

    def test_copy_not_empty(self, client, valid_payload):
        body = client.post("/ads/truck/", json=valid_payload).json()
        assert len(body["copy"]) > 0

    def test_campaign_id_string(self, client, valid_payload):
        body = client.post("/ads/truck/", json=valid_payload).json()
        assert isinstance(body["campaign_id"], str)
        assert body["campaign_id"].startswith("cmp_")

    def test_invalid_ano_returns_422(self, client, valid_payload):
        valid_payload["ano"] = "23"
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 422

    def test_invalid_budget_returns_422(self, client, valid_payload):
        valid_payload["budget"] = -10
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 422

    def test_invalid_genero_returns_422(self, client, valid_payload):
        valid_payload["publico_genero"] = "outros"
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 422

    def test_missing_required_field_returns_422(self, client, valid_payload):
        del valid_payload["modelo"]
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 422

    def test_idade_range_inverted_returns_422(self, client, valid_payload):
        valid_payload["publico_idade_min"] = 60
        valid_payload["publico_idade_max"] = 25
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 422


# ── GET /ads/truck ─────────────────────────────────────────────────────────────

class TestListCampaigns:
    def test_empty_list_on_fresh_service(self, client):
        r = client.get("/ads/truck/")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_published_campaign(self, client, valid_payload):
        client.post("/ads/truck/", json=valid_payload)
        items = client.get("/ads/truck/").json()
        assert len(items) == 1

    def test_list_item_has_frontend_contract_fields(self, client, valid_payload):
        client.post("/ads/truck/", json=valid_payload)
        item = client.get("/ads/truck/").json()[0]
        for field in ("id", "campaign_id", "modelo", "cor", "ano", "cidade",
                      "preco", "km", "status", "leads", "spend", "created"):
            assert field in item, f"Missing field: {field}"

    def test_status_returned_in_portuguese(self, client, valid_payload):
        client.post("/ads/truck/", json=valid_payload)
        item = client.get("/ads/truck/").json()[0]
        assert item["status"] == "rascunho"

    def test_filter_by_status_ativo(self, demo_client):
        items = demo_client.get("/ads/truck/?status=ativo").json()
        assert all(i["status"] == "ativo" for i in items)
        assert len(items) == 1

    def test_filter_by_status_pausado(self, demo_client):
        items = demo_client.get("/ads/truck/?status=pausado").json()
        assert all(i["status"] == "pausado" for i in items)

    def test_filter_by_nome(self, demo_client):
        items = demo_client.get("/ads/truck/?nome=Volvo").json()
        assert len(items) == 1
        assert "Volvo" in items[0]["modelo"]

    def test_filter_by_nome_case_insensitive(self, demo_client):
        items = demo_client.get("/ads/truck/?nome=volvo").json()
        assert len(items) == 1

    def test_demo_data_three_items(self, demo_client):
        items = demo_client.get("/ads/truck/").json()
        assert len(items) == 3

    def test_demo_volvo_has_correct_metrics(self, demo_client):
        items = demo_client.get("/ads/truck/").json()
        volvo = next(i for i in items if i["modelo"] == "Volvo FH 540")
        assert volvo["leads"] == 12
        assert volvo["spend"] == 150.50


# ── GET /ads/truck/{campaign_id} ───────────────────────────────────────────────

class TestGetCampaign:
    def test_returns_200_for_existing(self, client, valid_payload):
        campaign_id = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        r = client.get(f"/ads/truck/{campaign_id}")
        assert r.status_code == 200

    def test_returns_correct_modelo(self, client, valid_payload):
        campaign_id = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        body = client.get(f"/ads/truck/{campaign_id}").json()
        assert body["modelo"] == "Volvo FH 540"

    def test_returns_404_for_unknown(self, client):
        r = client.get("/ads/truck/cmp_does_not_exist")
        assert r.status_code == 404

    def test_404_body_has_error_fields(self, client):
        body = client.get("/ads/truck/cmp_ghost").json()
        assert body["error"] is True
        assert body["code"] == "CAMPAIGN_NOT_FOUND"
        assert "message" in body


# ── PATCH /ads/truck/{id}/pausar ──────────────────────────────────────────────

class TestPauseCampaign:
    def _create_and_activate(self, client, valid_payload) -> str:
        campaign_id = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        client.patch(f"/ads/truck/{campaign_id}/ativar")
        return campaign_id

    def test_pause_active_campaign(self, client, valid_payload):
        cid = self._create_and_activate(client, valid_payload)
        r = client.patch(f"/ads/truck/{cid}/pausar")
        assert r.status_code == 200
        assert r.json()["status"] == "pausado"

    def test_pause_returns_campaign_id(self, client, valid_payload):
        cid = self._create_and_activate(client, valid_payload)
        body = client.patch(f"/ads/truck/{cid}/pausar").json()
        assert body["campaign_id"] == cid

    def test_pause_draft_returns_409(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        r = client.patch(f"/ads/truck/{cid}/pausar")
        assert r.status_code == 409

    def test_pause_unknown_returns_404(self, client):
        r = client.patch("/ads/truck/cmp_ghost/pausar")
        assert r.status_code == 404


# ── PATCH /ads/truck/{id}/ativar ──────────────────────────────────────────────

class TestActivateCampaign:
    def test_activate_draft_campaign(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        r = client.patch(f"/ads/truck/{cid}/ativar")
        assert r.status_code == 200
        assert r.json()["status"] == "ativo"

    def test_activate_paused_campaign(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        client.patch(f"/ads/truck/{cid}/ativar")
        client.patch(f"/ads/truck/{cid}/pausar")
        r = client.patch(f"/ads/truck/{cid}/ativar")
        assert r.status_code == 200
        assert r.json()["status"] == "ativo"

    def test_activate_active_returns_409(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        client.patch(f"/ads/truck/{cid}/ativar")
        r = client.patch(f"/ads/truck/{cid}/ativar")
        assert r.status_code == 409

    def test_activate_unknown_returns_404(self, client):
        r = client.patch("/ads/truck/cmp_ghost/ativar")
        assert r.status_code == 404


# ── DELETE /ads/truck/{id} ────────────────────────────────────────────────────

class TestDeleteCampaign:
    def test_delete_returns_200(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        r = client.delete(f"/ads/truck/{cid}")
        assert r.status_code == 200

    def test_delete_response_shape(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        body = client.delete(f"/ads/truck/{cid}").json()
        assert body["deleted"] is True
        assert body["campaign_id"] == cid

    def test_deleted_campaign_returns_404_on_get(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        client.delete(f"/ads/truck/{cid}")
        r = client.get(f"/ads/truck/{cid}")
        assert r.status_code == 404

    def test_delete_unknown_returns_404(self, client):
        r = client.delete("/ads/truck/cmp_ghost")
        assert r.status_code == 404


# ── GET /ads/truck/{id}/metricas ──────────────────────────────────────────────

class TestGetMetrics:
    def test_returns_metrics_structure(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        body = client.get(f"/ads/truck/{cid}/metricas").json()
        for field in ("campaign_id", "impressions", "clicks", "leads", "spent", "cpl", "period"):
            assert field in body, f"Missing field: {field}"

    def test_default_period_is_last_7d(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        body = client.get(f"/ads/truck/{cid}/metricas").json()
        assert body["period"] == "last_7d"

    def test_custom_period_today(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        body = client.get(f"/ads/truck/{cid}/metricas?period=today").json()
        assert body["period"] == "today"

    def test_invalid_period_returns_422(self, client, valid_payload):
        cid = client.post("/ads/truck/", json=valid_payload).json()["campaign_id"]
        r = client.get(f"/ads/truck/{cid}/metricas?period=semana_passada")
        assert r.status_code == 422

    def test_unknown_campaign_returns_404(self, client):
        r = client.get("/ads/truck/cmp_ghost/metricas")
        assert r.status_code == 404

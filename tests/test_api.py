"""
Testes dos endpoints FastAPI — Truck Ads Manager.
Execute com: python -m pytest tests/test_api.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ads.providers.mock_provider import MockAdsProvider
from ads.truck.service import TruckAdService
from api.dependencies import get_truck_service
from api.main import create_app
from auth.dependencies import get_current_user
from db.models.user import User


# ── Mock user for auth bypass ──────────────────────────────────────────────────

def _mock_user() -> User:
    u = User.__new__(User)
    u.id = 1
    u.name = "Teste"
    u.email = "teste@example.com"
    u.is_active = True
    return u


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def service() -> TruckAdService:
    return TruckAdService(provider=MockAdsProvider())


@pytest.fixture
def client(service: TruckAdService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_truck_service] = lambda: service
    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def demo_client() -> TestClient:
    """Client pré-carregado com dados de demonstração."""
    provider = MockAdsProvider.with_demo_data()
    demo_service = TruckAdService(provider=provider)
    app = create_app()
    app.dependency_overrides[get_truck_service] = lambda: demo_service
    app.dependency_overrides[get_current_user] = _mock_user
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
                      "cidade", "copy", "headline", "budget", "created"):
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

    def test_enable_ai_copy_false_uses_template(self, client, valid_payload, monkeypatch):
        monkeypatch.setenv("ENABLE_AI_COPY", "false")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        body = client.post("/ads/truck/", json=valid_payload).json()
        assert body["status"] == "rascunho"
        assert len(body["copy"]) > 0

    def test_system_works_without_anthropic_key(self, client, valid_payload, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ENABLE_AI_COPY", raising=False)
        r = client.post("/ads/truck/", json=valid_payload)
        assert r.status_code == 201

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




# ── Helpers for auth-aware tests ──────────────────────────────────────────────

_TRUCK_PAYLOAD: dict = {
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


def _login_as(client: TestClient, test_db: Session, email: str, name: str = "User") -> str:
    """Register, verify email, login — returns access_token."""
    client.post("/auth/register", json={"name": name, "email": email, "password": "Senha1234"})
    user = test_db.query(User).filter_by(email=email).first()
    assert user is not None and user.email_verification_token is not None
    client.get(f"/auth/verify-email?token={user.email_verification_token}")
    r = client.post("/auth/login", json={"email": email, "password": "Senha1234"})
    return r.json()["access_token"]


# ── TestAuthRequired ───────────────────────────────────────────────────────────

class TestAuthRequired:
    """All truck endpoints must return 401 when called without a valid token."""

    def test_list_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.get("/ads/truck/")
        assert r.status_code == 401

    def test_create_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.post("/ads/truck/", json=_TRUCK_PAYLOAD)
        assert r.status_code == 401

    def test_get_detail_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.get("/ads/truck/cmp_any")
        assert r.status_code == 401

    def test_pause_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.patch("/ads/truck/cmp_any/pausar")
        assert r.status_code == 401

    def test_activate_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.patch("/ads/truck/cmp_any/ativar")
        assert r.status_code == 401

    def test_delete_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.delete("/ads/truck/cmp_any")
        assert r.status_code == 401

    def test_metrics_without_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.get("/ads/truck/cmp_any/metricas")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.get(
            "/ads/truck/",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert r.status_code == 401


# ── TestMultiTenantIsolation ──────────────────────────────────────────────────

class TestMultiTenantIsolation:
    """User A cannot see or modify User B's campaigns."""

    def test_list_campaigns_is_user_scoped(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        token_a = _login_as(auth_client, test_db, "usera@example.com", "User A")
        r = auth_client.post(
            "/ads/truck/",
            json=_TRUCK_PAYLOAD,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 201

        token_b = _login_as(auth_client, test_db, "userb@example.com", "User B")
        items = auth_client.get(
            "/ads/truck/",
            headers={"Authorization": f"Bearer {token_b}"},
        ).json()
        assert items == []

    def test_get_campaign_of_other_user_returns_404(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        token_a = _login_as(auth_client, test_db, "usera2@example.com", "User A2")
        campaign_id = auth_client.post(
            "/ads/truck/",
            json=_TRUCK_PAYLOAD,
            headers={"Authorization": f"Bearer {token_a}"},
        ).json()["campaign_id"]

        token_b = _login_as(auth_client, test_db, "userb2@example.com", "User B2")
        r = auth_client.get(
            f"/ads/truck/{campaign_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r.status_code == 404

    def test_delete_campaign_of_other_user_returns_404(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        token_a = _login_as(auth_client, test_db, "usera3@example.com", "User A3")
        campaign_id = auth_client.post(
            "/ads/truck/",
            json=_TRUCK_PAYLOAD,
            headers={"Authorization": f"Bearer {token_a}"},
        ).json()["campaign_id"]

        token_b = _login_as(auth_client, test_db, "userb3@example.com", "User B3")
        r = auth_client.delete(
            f"/ads/truck/{campaign_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r.status_code == 404

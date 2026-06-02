"""Tests for GET /ads/truck/{id}/metricas — real Meta Insights API integration.

All Meta API calls are mocked — no real HTTP requests are made.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

from ads.providers.meta.exceptions import MetaAPIError, MetaAuthError, MetaPermissionError, MetaRateLimitError
from db.models.user import User

_PATCH_META_TOKEN = "meta.routes.validate_meta_token"
_PATCH_META_ACCOUNT = "meta.routes.validate_ad_account"
_PATCH_META_PAGE = "meta.routes.validate_page"
_PATCH_PROVIDER = "api.routers.truck.MetaAdsProvider"

_CREDENTIAL_PAYLOAD = {
    "name": "Conta Métricas",
    "access_token": "EAABsbCS_metrics_test",
    "ad_account_id": "act_987654321",
    "page_id": "111111111",
}

_CAMPAIGN_PAYLOAD = {
    "modelo": "Scania R 450",
    "cor": "Vermelho",
    "ano": "2021",
    "preco": "280000",
    "km": "90000",
    "budget": 40.0,
    "duracao": 7,
    "vendedor_nome": "Maria Costa",
    "vendedor_wpp": "5541988880000",
    "cidade": "Porto Alegre",
    "estado": "RS",
    "publico_idade_min": 30,
    "publico_idade_max": 60,
    "publico_raio": 80,
    "publico_genero": "all",
    "publico_interesses": "caminhões,transporte",
    "publico_posicionamentos": ["feed"],
}

_MOCK_PUBLISH_RESULT = {
    "success": True,
    "message": "Ad published to Meta Ads",
    "campaign": {"id": "mc_aaa111", "name": "Test"},
    "adset": {"id": "ms_bbb222", "campaign_id": "mc_aaa111"},
    "ad": {
        "id": "ma_ccc333",
        "adset_id": "ms_bbb222",
        "creative_id": "cr_ddd444",
        "meta_id": "ma_ccc333",
    },
}

_MOCK_INSIGHTS = {
    "campaign_id": "mc_aaa111",
    "impressions": 5000,
    "reach": 4200,
    "clicks": 180,
    "leads": 12,
    "spent": 96.50,
    "cpl": 8.04,
    "cpc": 0.54,
    "cpm": 19.30,
    "ctr": 3.60,
    "source": "meta",
    "synced_at": "2026-06-02T12:00:00+00:00",
    "period": "last_7d",
}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(
    auth_client: "TestClient",
    test_db: "Session",
    email: str = "metrics@example.com",
    name: str = "Metrics User",
) -> str:
    auth_client.post("/auth/register", json={"name": name, "email": email, "password": "Senha1234"})
    user = test_db.query(User).filter_by(email=email).first()
    assert user is not None
    auth_client.get(f"/auth/verify-email?token={user.email_verification_token}")
    r = auth_client.post("/auth/login", json={"email": email, "password": "Senha1234"})
    assert r.status_code == 200, r.json()
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_credential(auth_client: "TestClient", token: str) -> int:
    with (
        patch(_PATCH_META_TOKEN, return_value={"id": "987", "name": "User"}),
        patch(_PATCH_META_ACCOUNT, return_value={"id": "act_987", "name": "Acc"}),
        patch(_PATCH_META_PAGE, return_value={"id": "111", "name": "Page"}),
    ):
        r = auth_client.post("/meta/credentials", json=_CREDENTIAL_PAYLOAD, headers=_auth(token))
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def _create_campaign(auth_client: "TestClient", token: str) -> str:
    r = auth_client.post("/ads/truck/", json=_CAMPAIGN_PAYLOAD, headers=_auth(token))
    assert r.status_code == 201, r.json()
    return r.json()["campaign_id"]


def _publish(auth_client: "TestClient", token: str, campaign_id: str, cred_id: int) -> None:
    with patch(_PATCH_PROVIDER) as mock_provider:
        mock_provider.return_value.publish_ad.return_value = _MOCK_PUBLISH_RESULT
        r = auth_client.post(
            f"/ads/truck/{campaign_id}/publish",
            json={"meta_credential_id": cred_id},
            headers=_auth(token),
        )
    assert r.status_code == 200, r.json()


def _get_metrics(
    auth_client: "TestClient",
    token: str,
    campaign_id: str,
    period: str = "last_7d",
    *,
    meta_raises: Exception | None = None,
    meta_returns: dict[str, Any] | None = None,
) -> Any:
    with patch(_PATCH_PROVIDER) as mock_provider:
        if meta_raises:
            mock_provider.return_value.get_campaign_insights.side_effect = meta_raises
        else:
            mock_provider.return_value.get_campaign_insights.return_value = (
                meta_returns or _MOCK_INSIGHTS
            )
        return auth_client.get(
            f"/ads/truck/{campaign_id}/metricas?period={period}",
            headers=_auth(token),
        )


# ── 1. Success — published campaign returns real metrics ───────────────────────


def test_metrics_published_campaign_success(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m1@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid)

    assert r.status_code == 200
    data = r.json()
    assert data["campaign_id"] == "mc_aaa111"
    assert data["impressions"] == 5000
    assert data["reach"] == 4200
    assert data["clicks"] == 180
    assert data["leads"] == 12
    assert data["source"] == "meta"
    assert "synced_at" in data


def test_metrics_response_has_all_required_fields(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m2@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid)

    data = r.json()
    for field in ("impressions", "reach", "clicks", "leads", "spent", "cpl", "cpc", "cpm", "ctr", "source", "synced_at", "period"):
        assert field in data, f"missing field: {field}"


# ── 2. Period parameter is forwarded ──────────────────────────────────────────


def test_metrics_period_today_forwarded(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m3@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        mock_provider.return_value.get_campaign_insights.return_value = {
            **_MOCK_INSIGHTS, "period": "today"
        }
        r = auth_client.get(f"/ads/truck/{cid}/metricas?period=today", headers=_auth(token))
        call_args = mock_provider.return_value.get_campaign_insights.call_args[0]
        assert call_args[1] == "today"

    assert r.status_code == 200
    assert r.json()["period"] == "today"


def test_metrics_period_last_30d_forwarded(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m4@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid, period="last_30d")

    assert r.status_code == 200


def test_metrics_invalid_period_returns_422(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m5@example.com")
    r = auth_client.get("/ads/truck/any_id/metricas?period=invalid", headers=_auth(token))
    assert r.status_code == 422


# ── 3. Unpublished campaign returns 409 ──────────────────────────────────────


def test_metrics_unpublished_campaign_returns_409(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m6@example.com")
    cid = _create_campaign(auth_client, token)

    r = auth_client.get(f"/ads/truck/{cid}/metricas", headers=_auth(token))

    assert r.status_code == 409
    assert "publicada" in r.json()["detail"].lower()


# ── 4. Unknown campaign returns 404 ──────────────────────────────────────────


def test_metrics_unknown_campaign_returns_404(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m7@example.com")
    r = auth_client.get("/ads/truck/cmp_nonexistent/metricas", headers=_auth(token))
    assert r.status_code == 404


# ── 5. Tenant isolation — user B cannot see user A's metrics ─────────────────


def test_metrics_wrong_user_returns_404(auth_client: "TestClient", test_db: "Session") -> None:
    token_a = _register_and_login(auth_client, test_db, "m8a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "m8b@example.com", "User B")

    cred_id = _create_credential(auth_client, token_a)
    cid = _create_campaign(auth_client, token_a)
    _publish(auth_client, token_a, cid, cred_id)

    r = auth_client.get(f"/ads/truck/{cid}/metricas", headers=_auth(token_b))
    assert r.status_code == 404


# ── 6. Meta permission error returns 403 ─────────────────────────────────────


def test_metrics_meta_permission_error_returns_403(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m9@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid, meta_raises=MetaPermissionError("ads_read missing", 10))

    assert r.status_code == 403


def test_metrics_meta_auth_error_returns_403(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m10@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid, meta_raises=MetaAuthError("Token expired", 190))

    assert r.status_code == 403


# ── 7. Rate limit returns 429 ─────────────────────────────────────────────────


def test_metrics_rate_limit_returns_429(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m11@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid, meta_raises=MetaRateLimitError("Rate limit", 4))

    assert r.status_code == 429


# ── 8. Generic Meta API error returns 400 ────────────────────────────────────


def test_metrics_meta_api_error_returns_400(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m12@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid, meta_raises=MetaAPIError("Bad request", 100))

    assert r.status_code == 400


# ── 9. Unexpected error returns 502 ──────────────────────────────────────────


def test_metrics_unexpected_error_returns_502(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m13@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid, meta_raises=RuntimeError("Unexpected failure"))

    assert r.status_code == 502


# ── 10. cpl is None when leads == 0 ──────────────────────────────────────────


def test_metrics_cpl_is_null_when_no_leads(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m14@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    zero_leads = {**_MOCK_INSIGHTS, "leads": 0, "cpl": None}
    r = _get_metrics(auth_client, token, cid, meta_returns=zero_leads)

    assert r.status_code == 200
    assert r.json()["leads"] == 0
    assert r.json()["cpl"] is None


def test_metrics_source_is_meta(auth_client: "TestClient", test_db: "Session") -> None:
    token = _register_and_login(auth_client, test_db, "m15@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    r = _get_metrics(auth_client, token, cid)

    assert r.json()["source"] == "meta"


def test_metrics_uses_meta_campaign_id_not_internal_id(auth_client: "TestClient", test_db: "Session") -> None:
    """Provider must be called with meta_campaign_id, not the internal campaign_id."""
    token = _register_and_login(auth_client, test_db, "m16@example.com")
    cred_id = _create_credential(auth_client, token)
    cid = _create_campaign(auth_client, token)
    _publish(auth_client, token, cid, cred_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        mock_provider.return_value.get_campaign_insights.return_value = _MOCK_INSIGHTS
        auth_client.get(f"/ads/truck/{cid}/metricas", headers=_auth(token))
        call_args = mock_provider.return_value.get_campaign_insights.call_args[0]
        # meta_campaign_id from _MOCK_PUBLISH_RESULT is "mc_aaa111"
        assert call_args[0] == "mc_aaa111"
        assert call_args[0] != cid

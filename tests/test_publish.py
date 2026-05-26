"""
Tests for POST /ads/truck/{campaign_id}/publish endpoint.

Meta Ads API calls are always mocked — no real HTTP requests are made.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models.campaign import CampaignModel
from db.models.user import User

# ── Constants ──────────────────────────────────────────────────────────────────

_MOCK_PUBLISH_RESULT = {
    "success": True,
    "message": "Ad published to Meta Ads",
    "campaign": {"id": "camp_111222333", "name": "Test Campaign"},
    "adset": {"id": "adset_444555666", "campaign_id": "camp_111222333"},
    "ad": {
        "id": "ad_777888999",
        "adset_id": "adset_444555666",
        "creative_id": "creative_000111222",
        "meta_id": "ad_777888999",
    },
}

_CREDENTIAL_PAYLOAD = {
    "name": "Conta Teste",
    "access_token": "EAABsbCS1234567890abcdef",
    "ad_account_id": "act_123456789",
    "page_id": "999999999",
}

_CAMPAIGN_PAYLOAD = {
    "modelo": "Volvo FH 540",
    "cor": "Branco",
    "ano": "2022",
    "preco": "350000",
    "km": "120000",
    "budget": 50.0,
    "duracao": 7,
    "vendedor_nome": "João Silva",
    "vendedor_wpp": "5541999990000",
    "cidade": "Curitiba",
    "estado": "PR",
    "publico_idade_min": 25,
    "publico_idade_max": 55,
    "publico_raio": 100,
    "publico_genero": "all",
    "publico_interesses": "caminhões,frete",
    "publico_posicionamentos": ["feed"],
}

_PATCH_META_TOKEN = "meta.routes.validate_meta_token"
_PATCH_META_ACCOUNT = "meta.routes.validate_ad_account"
_PATCH_META_PAGE = "meta.routes.validate_page"
_PATCH_PROVIDER = "api.routers.truck.MetaAdsProvider"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(
    client: TestClient,
    test_db: Session,
    email: str = "user@example.com",
    name: str = "Test User",
) -> str:
    client.post("/auth/register", json={"name": name, "email": email, "password": "Senha1234"})
    user = test_db.query(User).filter_by(email=email).first()
    assert user is not None
    client.get(f"/auth/verify-email?token={user.email_verification_token}")
    r = client.post("/auth/login", json={"email": email, "password": "Senha1234"})
    assert r.status_code == 200, r.json()
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_credential(client: TestClient, token: str) -> int:
    with (
        patch(_PATCH_META_TOKEN, return_value={"id": "123", "name": "User"}),
        patch(_PATCH_META_ACCOUNT, return_value={"id": "act_123", "name": "Acc"}),
        patch(_PATCH_META_PAGE, return_value={"id": "999", "name": "Page"}),
    ):
        r = client.post(
            "/meta/credentials",
            json=_CREDENTIAL_PAYLOAD,
            headers=_auth(token),
        )
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def _create_campaign(client: TestClient, token: str) -> str:
    r = client.post("/ads/truck/", json=_CAMPAIGN_PAYLOAD, headers=_auth(token))
    assert r.status_code == 201, r.json()
    return r.json()["campaign_id"]


def _publish(
    client: TestClient,
    token: str,
    campaign_id: str,
    cred_id: int,
    *,
    mock_result: dict | None = None,
) -> Any:
    result = mock_result or _MOCK_PUBLISH_RESULT
    with patch(_PATCH_PROVIDER) as MockProvider:
        instance = MockProvider.return_value
        instance.publish_ad.return_value = result
        r = client.post(
            f"/ads/truck/{campaign_id}/publish",
            json={"meta_credential_id": cred_id},
            headers=_auth(token),
        )
    return r


# ── Tests: happy path ──────────────────────────────────────────────────────────


def test_publish_success(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    r = _publish(auth_client, token, campaign_id, cred_id)
    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["campaign_id"] == campaign_id
    assert data["meta_status"] == "PAUSED"
    assert data["status"] == "pausado"


def test_publish_saves_meta_campaign_id(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    assert record.meta_campaign_id == "camp_111222333"


def test_publish_saves_meta_adset_id(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.meta_adset_id == "adset_444555666"


def test_publish_saves_meta_creative_id(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.meta_creative_id == "creative_000111222"


def test_publish_saves_meta_ad_id(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.meta_ad_id == "ad_777888999"


def test_publish_status_becomes_pausado(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.status == "pausado"
    assert record.meta_status == "PAUSED"


def test_publish_never_active(auth_client: TestClient, test_db: Session) -> None:
    """Campaign must never be set to ACTIVE after publish."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    r = _publish(auth_client, token, campaign_id, cred_id)
    data = r.json()
    assert data.get("meta_status") != "ACTIVE"
    assert data.get("status") != "ativo"

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.meta_status != "ACTIVE"
    assert record.status != "ativo"


def test_publish_saves_published_at(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.published_at is not None


def test_publish_saves_meta_credential_id(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.meta_credential_id == cred_id


def test_publish_creates_provider_with_credential_data(
    auth_client: TestClient, test_db: Session
) -> None:
    """MetaAdsProvider must be instantiated with the credential's access_token and ad_account_id."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    with patch(_PATCH_PROVIDER) as MockProvider:
        instance = MockProvider.return_value
        instance.publish_ad.return_value = _MOCK_PUBLISH_RESULT
        auth_client.post(
            f"/ads/truck/{campaign_id}/publish",
            json={"meta_credential_id": cred_id},
            headers=_auth(token),
        )
        call_kwargs = MockProvider.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("ad_account_id") == "act_123456789"
    assert call_kwargs.kwargs.get("page_id") == "999999999"
    # access_token must be present but we don't check its value (it's decrypted)
    assert "access_token" in call_kwargs.kwargs


# ── Tests: authentication & authorization ──────────────────────────────────────


def test_publish_requires_auth(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    campaign_id = _create_campaign(auth_client, token)
    cred_id = _create_credential(auth_client, token)

    r = auth_client.post(
        f"/ads/truck/{campaign_id}/publish",
        json={"meta_credential_id": cred_id},
    )
    assert r.status_code == 401


def test_publish_wrong_campaign(auth_client: TestClient, test_db: Session) -> None:
    """User B cannot publish User A's campaign."""
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")

    campaign_id = _create_campaign(auth_client, token_a)
    cred_id = _create_credential(auth_client, token_b)

    r = _publish(auth_client, token_b, campaign_id, cred_id)
    assert r.status_code == 404


def test_publish_wrong_credential(auth_client: TestClient, test_db: Session) -> None:
    """User B cannot use User A's credential to publish."""
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")

    campaign_id = _create_campaign(auth_client, token_b)
    cred_id_a = _create_credential(auth_client, token_a)

    r = _publish(auth_client, token_b, campaign_id, cred_id_a)
    assert r.status_code == 404


def test_publish_campaign_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)

    r = _publish(auth_client, token, "cmp_nonexistent", cred_id)
    assert r.status_code == 404


def test_publish_credential_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    campaign_id = _create_campaign(auth_client, token)

    r = _publish(auth_client, token, campaign_id, cred_id=99999)
    assert r.status_code == 404


# ── Tests: Meta API error handling ────────────────────────────────────────────


def test_publish_meta_api_error_returns_400(auth_client: TestClient, test_db: Session) -> None:
    from ads.providers.meta.exceptions import MetaAPIError

    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    with patch(_PATCH_PROVIDER) as MockProvider:
        instance = MockProvider.return_value
        instance.publish_ad.side_effect = MetaAPIError("Invalid ad account", code=100)
        r = auth_client.post(
            f"/ads/truck/{campaign_id}/publish",
            json={"meta_credential_id": cred_id},
            headers=_auth(token),
        )

    assert r.status_code == 400


def test_publish_meta_error_does_not_update_db(auth_client: TestClient, test_db: Session) -> None:
    """When Meta API fails, DB record must remain unchanged."""
    from ads.providers.meta.exceptions import MetaAPIError

    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    with patch(_PATCH_PROVIDER) as MockProvider:
        instance = MockProvider.return_value
        instance.publish_ad.side_effect = MetaAPIError("Forbidden", code=200)
        auth_client.post(
            f"/ads/truck/{campaign_id}/publish",
            json={"meta_credential_id": cred_id},
            headers=_auth(token),
        )

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record.meta_campaign_id is None
    assert record.status == "rascunho"


# ── Tests: security ────────────────────────────────────────────────────────────


def test_publish_response_has_no_access_token(auth_client: TestClient, test_db: Session) -> None:
    """access_token must never appear in the publish response."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    r = _publish(auth_client, token, campaign_id, cred_id)
    assert r.status_code == 200
    raw = r.text
    assert "access_token" not in raw
    assert "access_token_enc" not in raw
    assert _CREDENTIAL_PAYLOAD["access_token"] not in raw


def test_build_meta_payload_from_record_structure(
    auth_client: TestClient, test_db: Session
) -> None:
    """Verify the payload builder produces the expected structure."""
    from ads.truck.service import build_meta_payload_from_record

    token = _register_and_login(auth_client, test_db)
    _create_campaign(auth_client, token)

    record = test_db.query(CampaignModel).first()
    assert record is not None

    payload = build_meta_payload_from_record(record)

    assert "campaign" in payload
    assert "adset" in payload
    assert "ad" in payload
    assert payload["campaign"]["objective"] == "OUTCOME_LEADS"
    assert payload["adset"]["audience"]["age_min"] == 25
    assert payload["adset"]["audience"]["age_max"] == 55
    assert "Volvo FH 540" in payload["campaign"]["name"]
    assert "Volvo FH 540" in payload["ad"]["copy"]
    assert "access_token" not in str(payload)

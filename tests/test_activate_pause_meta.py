"""Tests for PATCH /ads/truck/{id}/ativar and /pausar via Meta Ads API.

Meta API calls are always mocked — no real HTTP requests are made.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

from ads.providers.meta.exceptions import MetaAPIError
from db.models.campaign import CampaignModel
from db.models.user import User

_PATCH_META_TOKEN = "meta.routes.validate_meta_token"
_PATCH_META_ACCOUNT = "meta.routes.validate_ad_account"
_PATCH_META_PAGE = "meta.routes.validate_page"
_PATCH_PROVIDER = "api.routers.truck.MetaAdsProvider"

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


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(
    client: TestClient,
    test_db: Session,
    email: str = "user@example.com",
    name: str = "Test User",
) -> str:
    client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "Senha1234"},
    )
    user = test_db.query(User).filter_by(email=email).first()
    assert user is not None
    client.get(f"/auth/verify-email?token={user.email_verification_token}")
    r = client.post("/auth/login", json={"email": email, "password": "Senha1234"})
    assert r.status_code == 200, r.json()
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
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
    mock_result: dict[str, Any] | None = None,
) -> Any:
    result = mock_result or _MOCK_PUBLISH_RESULT
    with patch(_PATCH_PROVIDER) as mock_provider:
        mock_provider.return_value.publish_ad.return_value = result
        r = client.post(
            f"/ads/truck/{campaign_id}/publish",
            json={"meta_credential_id": cred_id},
            headers=_auth(token),
        )
    assert r.status_code == 200, r.json()
    return r


def _ativar(
    client: TestClient,
    token: str,
    campaign_id: str,
    *,
    meta_raises: Exception | None = None,
) -> Any:
    with patch(_PATCH_PROVIDER) as mock_provider:
        if meta_raises:
            mock_provider.return_value.activate_ad.side_effect = meta_raises
        else:
            mock_provider.return_value.activate_ad.return_value = {"success": True}
        return client.patch(
            f"/ads/truck/{campaign_id}/ativar",
            headers=_auth(token),
        )


def _pausar(
    client: TestClient,
    token: str,
    campaign_id: str,
    *,
    meta_raises: Exception | None = None,
) -> Any:
    with patch(_PATCH_PROVIDER) as mock_provider:
        if meta_raises:
            mock_provider.return_value.pause_ad.side_effect = meta_raises
        else:
            mock_provider.return_value.pause_ad.return_value = {"success": True}
        return client.patch(
            f"/ads/truck/{campaign_id}/pausar",
            headers=_auth(token),
        )


# ── Tests: ativar ──────────────────────────────────────────────────────────────


def test_ativar_published_campaign_success(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """Activating a published campaign calls Meta API and updates DB."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    r = _ativar(auth_client, token, campaign_id)
    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["campaign_id"] == campaign_id
    assert data["status"] == "ativo"
    assert data["meta_status"] == "ACTIVE"


def test_ativar_updates_db_status(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    _ativar(auth_client, token, campaign_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    assert record.status == "ativo"
    assert record.meta_status == "ACTIVE"


def test_ativar_calls_meta_with_active_status(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """verify MetaAdsProvider.activate_ad() is called with the correct ad_id."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        mock_provider.return_value.activate_ad.return_value = {"success": True}
        auth_client.patch(f"/ads/truck/{campaign_id}/ativar", headers=_auth(token))
        mock_provider.return_value.activate_ad.assert_called_once_with("ad_777888999")


def test_ativar_rascunho_returns_409(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """Draft campaigns cannot be activated — must be published first."""
    token = _register_and_login(auth_client, test_db)
    campaign_id = _create_campaign(auth_client, token)

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/ativar", headers=_auth(token))
        mock_provider.return_value.activate_ad.assert_not_called()

    assert r.status_code == 409
    assert "publicada" in r.json()["detail"].lower()


def test_ativar_without_meta_ad_id_returns_409(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """Campaign without meta_ad_id (edge case) returns 409, Meta not called."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)

    # Publish with a result missing the ad id
    partial_result = {**_MOCK_PUBLISH_RESULT, "ad": {"id": None, "creative_id": None}}
    _publish(auth_client, token, campaign_id, cred_id, mock_result=partial_result)

    # Force meta_ad_id to None directly in DB
    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    record.meta_ad_id = None
    test_db.commit()

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/ativar", headers=_auth(token))
        mock_provider.return_value.activate_ad.assert_not_called()

    assert r.status_code == 409


def test_ativar_without_meta_credential_id_returns_409(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """Campaign without meta_credential_id returns 409, Meta not called."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    record.meta_credential_id = None
    test_db.commit()

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/ativar", headers=_auth(token))
        mock_provider.return_value.activate_ad.assert_not_called()

    assert r.status_code == 409


def test_ativar_wrong_user_returns_404(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """User B cannot activate User A's campaign."""
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")

    cred_id = _create_credential(auth_client, token_a)
    campaign_id = _create_campaign(auth_client, token_a)
    _publish(auth_client, token_a, campaign_id, cred_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/ativar", headers=_auth(token_b))
        mock_provider.return_value.activate_ad.assert_not_called()

    assert r.status_code == 404


def test_ativar_meta_api_error_returns_400(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """When Meta API fails, endpoint returns 400 and DB is not updated."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    r = _ativar(
        auth_client,
        token,
        campaign_id,
        meta_raises=MetaAPIError("Token inválido", code=190),
    )
    assert r.status_code == 400

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    assert record.status == "pausado"
    assert record.meta_status == "PAUSED"


def test_ativar_meta_error_does_not_update_db(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """DB must remain unchanged when Meta API fails during activation."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    _ativar(
        auth_client,
        token,
        campaign_id,
        meta_raises=MetaAPIError("Permissão negada", code=200),
    )

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    assert record.status != "ativo"
    assert record.meta_status != "ACTIVE"


def test_ativar_already_active_returns_409(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)
    _ativar(auth_client, token, campaign_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/ativar", headers=_auth(token))
        mock_provider.return_value.activate_ad.assert_not_called()

    assert r.status_code == 409


def test_ativar_response_has_no_access_token(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """access_token must never appear in the activate response."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    r = _ativar(auth_client, token, campaign_id)
    assert r.status_code == 200
    assert "access_token" not in r.text
    assert "access_token_enc" not in r.text


# ── Tests: pausar ──────────────────────────────────────────────────────────────


def test_pausar_active_campaign_success(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    """Pausing an active campaign calls Meta API and updates DB."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)
    _ativar(auth_client, token, campaign_id)

    r = _pausar(auth_client, token, campaign_id)
    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["status"] == "pausado"
    assert data["meta_status"] == "PAUSED"


def test_pausar_updates_db_status(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)
    _ativar(auth_client, token, campaign_id)

    _pausar(auth_client, token, campaign_id)

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    assert record.status == "pausado"
    assert record.meta_status == "PAUSED"


def test_pausar_calls_meta_with_paused_status(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)
    _ativar(auth_client, token, campaign_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        mock_provider.return_value.pause_ad.return_value = {"success": True}
        auth_client.patch(f"/ads/truck/{campaign_id}/pausar", headers=_auth(token))
        mock_provider.return_value.pause_ad.assert_called_once_with("ad_777888999")


def test_pausar_rascunho_returns_409(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    campaign_id = _create_campaign(auth_client, token)

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/pausar", headers=_auth(token))
        mock_provider.return_value.pause_ad.assert_not_called()

    assert r.status_code == 409


def test_pausar_already_paused_returns_409(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/pausar", headers=_auth(token))
        mock_provider.return_value.pause_ad.assert_not_called()

    assert r.status_code == 409


def test_pausar_wrong_user_returns_404(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")

    cred_id = _create_credential(auth_client, token_a)
    campaign_id = _create_campaign(auth_client, token_a)
    _publish(auth_client, token_a, campaign_id, cred_id)
    _ativar(auth_client, token_a, campaign_id)

    with patch(_PATCH_PROVIDER) as mock_provider:
        r = auth_client.patch(f"/ads/truck/{campaign_id}/pausar", headers=_auth(token_b))
        mock_provider.return_value.pause_ad.assert_not_called()

    assert r.status_code == 404


def test_pausar_meta_api_error_returns_400(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)
    _ativar(auth_client, token, campaign_id)

    r = _pausar(
        auth_client,
        token,
        campaign_id,
        meta_raises=MetaAPIError("Rate limit", code=17),
    )
    assert r.status_code == 400

    test_db.expire_all()
    record = test_db.query(CampaignModel).filter_by(campaign_id=campaign_id).first()
    assert record is not None
    assert record.status == "ativo"
    assert record.meta_status == "ACTIVE"


def test_pausar_response_has_no_access_token(
    auth_client: TestClient,
    test_db: Session,
) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token)
    campaign_id = _create_campaign(auth_client, token)
    _publish(auth_client, token, campaign_id, cred_id)
    _ativar(auth_client, token, campaign_id)

    r = _pausar(auth_client, token, campaign_id)
    assert r.status_code == 200
    assert "access_token" not in r.text
    assert "access_token_enc" not in r.text

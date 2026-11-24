"""
Tests for /meta/credentials endpoints.

Meta API calls are always mocked — no real HTTP requests are made.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from auth.crypto import decrypt
from db.models.meta_credential import MetaCredential
from db.models.user import User

_MOCK_ME = {"id": "111111111", "name": "Test Meta User"}
_MOCK_ACCOUNT = {"id": "act_123456789", "name": "Test Ad Account", "account_status": 1}
_MOCK_PAGE = {"id": "999999999", "name": "Test Page", "category": "Automotive"}

_VALID_PAYLOAD = {
    "name": "Loja Caminhões Sul",
    "access_token": "EAABsbCS1234567890abcdef",
    "ad_account_id": "act_123456789",
    "page_id": "999999999",
    "instagram_actor_id": None,
    "whatsapp_phone_number": "5541999999999",
    "whatsapp_business_account_id": None,
}

_PATCH_VALIDATE_META = "meta.routes.validate_meta_token"
_PATCH_VALIDATE_ACCOUNT = "meta.routes.validate_ad_account"
_PATCH_VALIDATE_PAGE = "meta.routes.validate_page"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(
    client: TestClient,
    test_db: Session,
    email: str = "user@example.com",
    name: str = "Test User",
) -> str:
    """Register, verify email, log in, return access token."""
    client.post("/auth/register", json={"name": name, "email": email, "password": "Senha1234"})
    user = test_db.query(User).filter_by(email=email).first()
    assert user is not None
    client.get(f"/auth/verify-email?token={user.email_verification_token}")
    r = client.post("/auth/login", json={"email": email, "password": "Senha1234"})
    assert r.status_code == 200, r.json()
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_credential(client: TestClient, token: str, payload: dict | None = None) -> dict:
    """POST /meta/credentials with mocked Meta validation. Returns response JSON."""
    body = payload or _VALID_PAYLOAD
    with (
        patch(_PATCH_VALIDATE_META, return_value=_MOCK_ME),
        patch(_PATCH_VALIDATE_ACCOUNT, return_value=_MOCK_ACCOUNT),
        patch(_PATCH_VALIDATE_PAGE, return_value=_MOCK_PAGE),
    ):
        r = client.post("/meta/credentials", json=body, headers=_auth_headers(token))
    return r


# ── Tests: create ──────────────────────────────────────────────────────────────


def test_create_credential_valid(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = _create_credential(auth_client, token)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Loja Caminhões Sul"
    assert data["ad_account_id"] == "act_123456789"
    assert data["is_active"] is False


def test_create_credential_token_encrypted_in_db(auth_client: TestClient, test_db: Session) -> None:
    """Access token must be stored encrypted — never as plaintext."""
    token = _register_and_login(auth_client, test_db)
    r = _create_credential(auth_client, token)
    assert r.status_code == 201

    cred = test_db.query(MetaCredential).first()
    assert cred is not None
    assert cred.access_token_enc != _VALID_PAYLOAD["access_token"]
    decrypted = decrypt(cred.access_token_enc)
    assert decrypted == _VALID_PAYLOAD["access_token"]


def test_create_credential_token_not_in_response(auth_client: TestClient, test_db: Session) -> None:
    """API must never return access_token or access_token_enc."""
    token = _register_and_login(auth_client, test_db)
    r = _create_credential(auth_client, token)
    assert r.status_code == 201
    body = r.json()
    assert "access_token" not in body
    assert "access_token_enc" not in body


def test_create_credential_invalid_token(auth_client: TestClient, test_db: Session) -> None:
    """Reject creation when Meta validation fails."""
    from ads.providers.meta.credentials import MetaTokenError

    token = _register_and_login(auth_client, test_db)
    with patch(_PATCH_VALIDATE_META, side_effect=MetaTokenError("Token inválido", 400)):
        r = auth_client.post(
            "/meta/credentials", json=_VALID_PAYLOAD, headers=_auth_headers(token)
        )
    assert r.status_code == 400
    assert test_db.query(MetaCredential).count() == 0


def test_create_credential_normalizes_ad_account_id(
    auth_client: TestClient, test_db: Session
) -> None:
    """ad_account_id without act_ prefix must be stored as act_<id>."""
    token = _register_and_login(auth_client, test_db)
    payload = {**_VALID_PAYLOAD, "ad_account_id": "123456789"}
    r = _create_credential(auth_client, token, payload)
    assert r.status_code == 201
    assert r.json()["ad_account_id"] == "act_123456789"


def test_create_credential_requires_auth(auth_client: TestClient) -> None:
    r = auth_client.post("/meta/credentials", json=_VALID_PAYLOAD)
    assert r.status_code == 401


# ── Tests: list ────────────────────────────────────────────────────────────────


def test_list_credentials_empty(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = auth_client.get("/meta/credentials", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.json() == []


def test_list_credentials_no_token_exposed(auth_client: TestClient, test_db: Session) -> None:
    """Listing must never expose access_token or access_token_enc."""
    token = _register_and_login(auth_client, test_db)
    _create_credential(auth_client, token)

    r = auth_client.get("/meta/credentials", headers=_auth_headers(token))
    assert r.status_code == 200
    for item in r.json():
        assert "access_token" not in item
        assert "access_token_enc" not in item


def test_list_credentials_isolation(auth_client: TestClient, test_db: Session) -> None:
    """User A must not see User B's credentials."""
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")

    _create_credential(auth_client, token_a)

    r = auth_client.get("/meta/credentials", headers=_auth_headers(token_b))
    assert r.status_code == 200
    assert r.json() == []


# ── Tests: get by ID ───────────────────────────────────────────────────────────


def test_get_credential(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    r = auth_client.get(f"/meta/credentials/{cred_id}", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.json()["id"] == cred_id


def test_get_credential_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = auth_client.get("/meta/credentials/99999", headers=_auth_headers(token))
    assert r.status_code == 404


def test_get_credential_isolation(auth_client: TestClient, test_db: Session) -> None:
    """User B must get 404 when requesting User A's credential."""
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")

    cred_id = _create_credential(auth_client, token_a).json()["id"]

    r = auth_client.get(f"/meta/credentials/{cred_id}", headers=_auth_headers(token_b))
    assert r.status_code == 404


# ── Tests: update ──────────────────────────────────────────────────────────────


def test_update_credential_name(auth_client: TestClient, test_db: Session) -> None:
    """Updating only the name does not re-validate the token."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    r = auth_client.patch(
        f"/meta/credentials/{cred_id}",
        json={"name": "Novo Nome"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Novo Nome"


def test_update_credential_access_token_validates(auth_client: TestClient, test_db: Session) -> None:
    """Updating the token must re-run Meta validation."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    new_token = "EAABnewtoken9876543210"
    with (
        patch(_PATCH_VALIDATE_META, return_value=_MOCK_ME),
        patch(_PATCH_VALIDATE_ACCOUNT, return_value=_MOCK_ACCOUNT),
        patch(_PATCH_VALIDATE_PAGE, return_value=_MOCK_PAGE),
    ):
        r = auth_client.patch(
            f"/meta/credentials/{cred_id}",
            json={"access_token": new_token},
            headers=_auth_headers(token),
        )
    assert r.status_code == 200

    cred = test_db.query(MetaCredential).filter_by(id=cred_id).first()
    assert decrypt(cred.access_token_enc) == new_token


def test_update_credential_invalid_token_rejected(auth_client: TestClient, test_db: Session) -> None:
    from ads.providers.meta.credentials import MetaTokenError

    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    with patch(_PATCH_VALIDATE_META, side_effect=MetaTokenError("Token expirado", 400)):
        r = auth_client.patch(
            f"/meta/credentials/{cred_id}",
            json={"access_token": "expired_token_abc"},
            headers=_auth_headers(token),
        )
    assert r.status_code == 400


def test_update_credential_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = auth_client.patch(
        "/meta/credentials/99999",
        json={"name": "Novo Nome"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 404


def test_update_credential_isolation(auth_client: TestClient, test_db: Session) -> None:
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")
    cred_id = _create_credential(auth_client, token_a).json()["id"]

    r = auth_client.patch(
        f"/meta/credentials/{cred_id}",
        json={"name": "Hackeado"},
        headers=_auth_headers(token_b),
    )
    assert r.status_code == 404


# ── Tests: delete ──────────────────────────────────────────────────────────────


def test_delete_credential(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    r = auth_client.delete(f"/meta/credentials/{cred_id}", headers=_auth_headers(token))
    assert r.status_code == 204
    assert test_db.query(MetaCredential).filter_by(id=cred_id).first() is None


def test_delete_credential_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = auth_client.delete("/meta/credentials/99999", headers=_auth_headers(token))
    assert r.status_code == 404


def test_delete_credential_isolation(auth_client: TestClient, test_db: Session) -> None:
    """User B must not be able to delete User A's credential."""
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")
    cred_id = _create_credential(auth_client, token_a).json()["id"]

    r = auth_client.delete(f"/meta/credentials/{cred_id}", headers=_auth_headers(token_b))
    assert r.status_code == 404
    assert test_db.query(MetaCredential).filter_by(id=cred_id).first() is not None


# ── Tests: set-active ──────────────────────────────────────────────────────────


def test_set_active(auth_client: TestClient, test_db: Session) -> None:
    """set-active must activate the target and deactivate all others."""
    token = _register_and_login(auth_client, test_db)
    id1 = _create_credential(auth_client, token).json()["id"]
    id2 = _create_credential(auth_client, token, {**_VALID_PAYLOAD, "name": "Loja 2"}).json()["id"]

    r = auth_client.post(f"/meta/credentials/{id1}/set-active", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    test_db.expire_all()
    cred1 = test_db.query(MetaCredential).filter_by(id=id1).first()
    cred2 = test_db.query(MetaCredential).filter_by(id=id2).first()
    assert cred1.is_active is True
    assert cred2.is_active is False


def test_set_active_switches_correctly(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    id1 = _create_credential(auth_client, token).json()["id"]
    id2 = _create_credential(auth_client, token, {**_VALID_PAYLOAD, "name": "Loja 2"}).json()["id"]

    auth_client.post(f"/meta/credentials/{id1}/set-active", headers=_auth_headers(token))
    auth_client.post(f"/meta/credentials/{id2}/set-active", headers=_auth_headers(token))

    test_db.expire_all()
    assert test_db.query(MetaCredential).filter_by(id=id1).first().is_active is False
    assert test_db.query(MetaCredential).filter_by(id=id2).first().is_active is True


def test_set_active_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = auth_client.post("/meta/credentials/99999/set-active", headers=_auth_headers(token))
    assert r.status_code == 404


def test_set_active_isolation(auth_client: TestClient, test_db: Session) -> None:
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")
    cred_id = _create_credential(auth_client, token_a).json()["id"]

    r = auth_client.post(
        f"/meta/credentials/{cred_id}/set-active", headers=_auth_headers(token_b)
    )
    assert r.status_code == 404


# ── Tests: validate endpoint ───────────────────────────────────────────────────


def test_validate_credential_valid(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    with (
        patch(_PATCH_VALIDATE_META, return_value=_MOCK_ME),
        patch(_PATCH_VALIDATE_ACCOUNT, return_value=_MOCK_ACCOUNT),
        patch(_PATCH_VALIDATE_PAGE, return_value=_MOCK_PAGE),
    ):
        r = auth_client.post(
            f"/meta/credentials/{cred_id}/validate", headers=_auth_headers(token)
        )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["meta_user_id"] == "111111111"
    assert data["ad_account_name"] == "Test Ad Account"
    assert data["page_name"] == "Test Page"
    assert "access_token" not in data
    assert "access_token_enc" not in data


def test_validate_credential_invalid(auth_client: TestClient, test_db: Session) -> None:
    from ads.providers.meta.credentials import MetaTokenError

    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]

    with patch(_PATCH_VALIDATE_META, side_effect=MetaTokenError("Token expirado", 400)):
        r = auth_client.post(
            f"/meta/credentials/{cred_id}/validate", headers=_auth_headers(token)
        )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False
    assert "Token expirado" in data["message"]


def test_validate_credential_not_found(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    r = auth_client.post("/meta/credentials/99999/validate", headers=_auth_headers(token))
    assert r.status_code == 404


def test_validate_credential_isolation(auth_client: TestClient, test_db: Session) -> None:
    token_a = _register_and_login(auth_client, test_db, "a@example.com", "User A")
    token_b = _register_and_login(auth_client, test_db, "b@example.com", "User B")
    cred_id = _create_credential(auth_client, token_a).json()["id"]

    r = auth_client.post(
        f"/meta/credentials/{cred_id}/validate", headers=_auth_headers(token_b)
    )
    assert r.status_code == 404


# ── Tests: security guarantees ─────────────────────────────────────────────────


def test_access_token_never_plaintext_in_db(auth_client: TestClient, test_db: Session) -> None:
    token = _register_and_login(auth_client, test_db)
    _create_credential(auth_client, token)

    cred = test_db.query(MetaCredential).first()
    assert cred is not None
    raw_token = _VALID_PAYLOAD["access_token"]
    assert cred.access_token_enc != raw_token
    assert raw_token not in cred.access_token_enc


def test_access_token_never_in_any_response(auth_client: TestClient, test_db: Session) -> None:
    """Cross-check all read endpoints to ensure token never leaks."""
    token = _register_and_login(auth_client, test_db)
    cred_id = _create_credential(auth_client, token).json()["id"]
    raw_token = _VALID_PAYLOAD["access_token"]

    endpoints = [
        ("GET", "/meta/credentials"),
        ("GET", f"/meta/credentials/{cred_id}"),
    ]
    for method, url in endpoints:
        r = auth_client.request(method, url, headers=_auth_headers(token))
        assert r.status_code == 200
        assert raw_token not in r.text, f"Token leaked in {method} {url}"
        assert "access_token_enc" not in r.text, f"Encrypted token leaked in {method} {url}"

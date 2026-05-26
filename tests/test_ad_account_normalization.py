"""
Tests for ad_account_id normalization logic.

Covers:
- normalize_ad_account_id() in ads/providers/meta/credentials.py
- MetaAPIClient account_path property
- POST /meta/credentials route normalization
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ads.providers.meta.client import MetaAPIClient
from ads.providers.meta.credentials import normalize_ad_account_id
from db.models.user import User

_PATCH_META_TOKEN = "meta.routes.validate_meta_token"
_PATCH_META_ACCOUNT = "meta.routes.validate_ad_account"
_PATCH_META_PAGE = "meta.routes.validate_page"

_MOCK_ME = {"id": "111111111", "name": "Test Meta User"}
_MOCK_ACCOUNT = {"id": "act_123456789", "name": "Test Ad Account", "account_status": 1}
_MOCK_PAGE = {"id": "999999999", "name": "Test Page", "category": "Automotive"}


# ── normalize_ad_account_id ─────────────────────────────────────────────────────


def test_normalize_plain_numeric() -> None:
    assert normalize_ad_account_id("123456789") == "act_123456789"


def test_normalize_already_prefixed() -> None:
    assert normalize_ad_account_id("act_123456789") == "act_123456789"


def test_normalize_strips_whitespace() -> None:
    assert normalize_ad_account_id("  act_123456789  ") == "act_123456789"


def test_normalize_double_prefix() -> None:
    assert normalize_ad_account_id("act_act_123456789") == "act_123456789"


def test_normalize_empty_raises() -> None:
    with pytest.raises(ValueError):
        normalize_ad_account_id("")


def test_normalize_act_only_raises() -> None:
    with pytest.raises(ValueError):
        normalize_ad_account_id("act_")


def test_normalize_whitespace_only_raises() -> None:
    with pytest.raises(ValueError):
        normalize_ad_account_id("   ")


# ── MetaAPIClient.account_path ──────────────────────────────────────────────────


def test_client_plain_numeric() -> None:
    client = MetaAPIClient(access_token="tok", ad_account_id="123456789")
    assert client.account_path == "act_123456789"
    client.close()


def test_client_already_prefixed_no_double() -> None:
    client = MetaAPIClient(access_token="tok", ad_account_id="act_123456789")
    assert client.account_path == "act_123456789"
    client.close()


def test_client_double_prefix_stripped() -> None:
    client = MetaAPIClient(access_token="tok", ad_account_id="act_act_123456789")
    assert client.account_path == "act_123456789"
    client.close()


# ── POST /meta/credentials — route normalization ────────────────────────────────


def _register_and_login(
    client: TestClient,
    test_db: Session,
    email: str = "norm@example.com",
    name: str = "Norm User",
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


def _create_credential_with_account(
    client: TestClient, token: str, ad_account_id: str
) -> dict:
    payload = {
        "name": "Loja Teste",
        "access_token": "EAABsbCS1234567890abcdef",
        "ad_account_id": ad_account_id,
        "page_id": "999999999",
    }
    with (
        patch(_PATCH_META_TOKEN, return_value=_MOCK_ME),
        patch(_PATCH_META_ACCOUNT, return_value=_MOCK_ACCOUNT),
        patch(_PATCH_META_PAGE, return_value=_MOCK_PAGE),
    ):
        r = client.post("/meta/credentials", json=payload, headers=_auth(token))
    return r


def test_route_stores_act_prefix_for_plain_numeric(
    auth_client: TestClient, test_db: Session
) -> None:
    """POST /meta/credentials with ad_account_id='123456789' must store 'act_123456789'."""
    token = _register_and_login(auth_client, test_db)
    r = _create_credential_with_account(auth_client, token, "123456789")
    assert r.status_code == 201, r.json()
    assert r.json()["ad_account_id"] == "act_123456789"


def test_route_no_double_prefix_for_already_prefixed(
    auth_client: TestClient, test_db: Session
) -> None:
    """POST /meta/credentials with ad_account_id='act_123456789' must NOT store 'act_act_...'."""
    token = _register_and_login(auth_client, test_db, "norm2@example.com", "Norm User 2")
    r = _create_credential_with_account(auth_client, token, "act_123456789")
    assert r.status_code == 201, r.json()
    assert r.json()["ad_account_id"] == "act_123456789"

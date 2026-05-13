"""
Testes dos endpoints de autenticação — POST /auth/register, /login, /refresh, /me.
Execute com: python -m pytest tests/test_auth.py -v
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

_ALGORITHM = "HS256"
_ACCESS_SECRET = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET_KEY", "dev-refresh-secret-change-in-production")


# ── helpers ────────────────────────────────────────────────────────────────────


def _expired_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    return jwt.encode(payload, _ACCESS_SECRET, algorithm=_ALGORITHM)


def _register(client: TestClient, email: str = "user@example.com") -> dict:
    r = client.post(
        "/auth/register",
        json={"name": "Test User", "email": email, "password": "Senha1234"},
    )
    return r.json()


# ── POST /auth/register ────────────────────────────────────────────────────────


class TestRegister:
    def test_returns_201(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/register",
            json={"name": "Ana", "email": "ana@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 201

    def test_returns_tokens(self, auth_client: TestClient) -> None:
        body = _register(auth_client)
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_access_token_is_valid_jwt(self, auth_client: TestClient) -> None:
        body = _register(auth_client)
        payload = jwt.decode(body["access_token"], _ACCESS_SECRET, algorithms=[_ALGORITHM])
        assert payload["type"] == "access"
        assert "sub" in payload

    def test_refresh_token_is_valid_jwt(self, auth_client: TestClient) -> None:
        body = _register(auth_client)
        payload = jwt.decode(body["refresh_token"], _REFRESH_SECRET, algorithms=[_ALGORITHM])
        assert payload["type"] == "refresh"

    def test_duplicate_email_returns_409(self, auth_client: TestClient) -> None:
        _register(auth_client)
        r = auth_client.post(
            "/auth/register",
            json={"name": "Outro", "email": "user@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 409

    def test_email_case_insensitive_duplicate(self, auth_client: TestClient) -> None:
        _register(auth_client, "User@Example.COM")
        r = auth_client.post(
            "/auth/register",
            json={"name": "B", "email": "user@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 409

    def test_short_password_returns_422(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/register",
            json={"name": "X", "email": "x@example.com", "password": "1234567"},
        )
        assert r.status_code == 422

    def test_invalid_email_returns_422(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/register",
            json={"name": "X", "email": "not-an-email", "password": "Senha1234"},
        )
        assert r.status_code == 422

    def test_missing_field_returns_422(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/register",
            json={"name": "X", "password": "Senha1234"},
        )
        assert r.status_code == 422


# ── POST /auth/login ───────────────────────────────────────────────────────────


class TestLogin:
    def test_returns_200_with_tokens(self, auth_client: TestClient) -> None:
        _register(auth_client)
        r = auth_client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_wrong_password_returns_401(self, auth_client: TestClient) -> None:
        _register(auth_client)
        r = auth_client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )
        assert r.status_code == 401

    def test_unknown_email_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 401

    def test_email_case_insensitive_login(self, auth_client: TestClient) -> None:
        _register(auth_client, "myuser@example.com")
        r = auth_client.post(
            "/auth/login",
            json={"email": "MYUSER@EXAMPLE.COM", "password": "Senha1234"},
        )
        assert r.status_code == 200

    def test_missing_field_returns_422(self, auth_client: TestClient) -> None:
        r = auth_client.post("/auth/login", json={"email": "a@a.com"})
        assert r.status_code == 422


# ── POST /auth/refresh ─────────────────────────────────────────────────────────


class TestRefresh:
    def test_returns_new_access_token(self, auth_client: TestClient) -> None:
        tokens = _register(auth_client)
        r = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_also_rotates_refresh_token(self, auth_client: TestClient) -> None:
        tokens = _register(auth_client)
        r = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert r.json()["refresh_token"] != tokens["access_token"]

    def test_invalid_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": "not.a.valid.token"},
        )
        assert r.status_code == 401

    def test_access_token_as_refresh_returns_401(self, auth_client: TestClient) -> None:
        tokens = _register(auth_client)
        r = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert r.status_code == 401


# ── GET /auth/me ───────────────────────────────────────────────────────────────


class TestMe:
    def test_returns_user_data(self, auth_client: TestClient) -> None:
        tokens = _register(auth_client, "me@example.com")
        r = auth_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "me@example.com"
        assert body["name"] == "Test User"
        assert body["is_active"] is True
        assert body["is_verified"] is False

    def test_response_has_required_fields(self, auth_client: TestClient) -> None:
        tokens = _register(auth_client)
        body = auth_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).json()
        for field in ("id", "name", "email", "is_active", "is_verified", "created_at"):
            assert field in body, f"Missing field: {field}"

    def test_no_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.get("/auth/me")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, auth_client: TestClient) -> None:
        r = auth_client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert r.status_code == 401

    def test_expired_token_returns_401(self, auth_client: TestClient) -> None:
        tokens = _register(auth_client)
        # Decode sub to get user_id, then forge an expired token
        payload = jwt.decode(
            tokens["access_token"], _ACCESS_SECRET, algorithms=[_ALGORITHM]
        )
        expired = _expired_access_token(int(payload["sub"]))
        r = auth_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert r.status_code == 401


# ── POST /auth/logout ──────────────────────────────────────────────────────────


class TestLogout:
    def test_returns_ok(self, auth_client: TestClient) -> None:
        r = auth_client.post("/auth/logout")
        assert r.status_code == 200
        assert r.json()["ok"] is True

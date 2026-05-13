"""
Testes dos endpoints de autenticação — register, verify-email, login, refresh, me.
Execute com: python -m pytest tests/test_auth.py -v
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from db.models.user import User

_ALGORITHM = "HS256"
_ACCESS_SECRET = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
_REFRESH_SECRET = os.getenv(
    "JWT_REFRESH_SECRET_KEY", "dev-refresh-secret-change-in-production"
)

# ── helpers ────────────────────────────────────────────────────────────────────


def _expired_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    return jwt.encode(payload, _ACCESS_SECRET, algorithm=_ALGORITHM)


def _register(
    client: TestClient,
    email: str = "user@example.com",
    name: str = "Test User",
) -> dict:
    """POST /auth/register — returns RegisterResponse (message/email, NOT tokens)."""
    r = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "Senha1234"},
    )
    return r.json()


def _verify_email(client: TestClient, test_db: Session, email: str = "user@example.com") -> None:
    """Retrieve the verification token from DB and call GET /auth/verify-email."""
    user = test_db.query(User).filter_by(email=email).first()
    assert user is not None, f"User {email!r} not found in test DB"
    assert user.email_verification_token is not None
    r = client.get(f"/auth/verify-email?token={user.email_verification_token}")
    assert r.status_code == 200, f"verify-email failed: {r.json()}"


def _login(client: TestClient, email: str = "user@example.com") -> dict:
    """POST /auth/login — returns TokenResponse."""
    r = client.post(
        "/auth/login",
        json={"email": email, "password": "Senha1234"},
    )
    return r.json()


def _full_register(
    client: TestClient,
    test_db: Session,
    email: str = "user@example.com",
) -> dict:
    """Register + verify + login — returns TokenResponse."""
    _register(client, email)
    _verify_email(client, test_db, email)
    return _login(client, email)


# ── POST /auth/register ────────────────────────────────────────────────────────


class TestRegister:
    def test_returns_201(self, auth_client: TestClient) -> None:
        r = auth_client.post(
            "/auth/register",
            json={"name": "Ana", "email": "ana@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 201

    def test_response_has_message_and_email(self, auth_client: TestClient) -> None:
        body = _register(auth_client)
        assert "message" in body
        assert body["email"] == "user@example.com"
        assert "email_sent" in body

    def test_no_tokens_in_response(self, auth_client: TestClient) -> None:
        body = _register(auth_client)
        assert "access_token" not in body
        assert "refresh_token" not in body

    def test_user_created_as_unverified(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        assert user.is_verified is False

    def test_verification_token_stored_in_db(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        assert user.email_verification_token is not None
        assert len(user.email_verification_token) > 10
        assert user.email_verification_expires_at is not None

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


# ── GET /auth/verify-email ─────────────────────────────────────────────────────


class TestVerifyEmail:
    def test_valid_token_returns_200(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        r = auth_client.get(f"/auth/verify-email?token={user.email_verification_token}")
        assert r.status_code == 200
        assert r.json()["verified"] is True

    def test_user_is_verified_after_confirmation(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        _verify_email(auth_client, test_db)
        test_db.expire_all()
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        assert user.is_verified is True

    def test_token_cleared_after_use(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        _verify_email(auth_client, test_db)
        test_db.expire_all()
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        assert user.email_verification_token is None
        assert user.email_verification_expires_at is None

    def test_invalid_token_returns_400(self, auth_client: TestClient) -> None:
        r = auth_client.get("/auth/verify-email?token=totally-invalid-token")
        assert r.status_code == 400

    def test_token_cannot_be_reused(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        token = user.email_verification_token
        auth_client.get(f"/auth/verify-email?token={token}")
        r = auth_client.get(f"/auth/verify-email?token={token}")
        assert r.status_code == 400

    def test_expired_token_returns_400(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        user = test_db.query(User).filter_by(email="user@example.com").first()
        assert user is not None
        # Force token to be expired
        user.email_verification_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        test_db.commit()
        r = auth_client.get(f"/auth/verify-email?token={user.email_verification_token}")
        assert r.status_code == 400


# ── POST /auth/login ───────────────────────────────────────────────────────────


class TestLogin:
    def test_verified_user_can_login(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db)
        assert "access_token" in tokens
        assert "refresh_token" in tokens

    def test_unverified_user_blocked_returns_403(
        self, auth_client: TestClient
    ) -> None:
        _register(auth_client)
        r = auth_client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "Senha1234"},
        )
        assert r.status_code == 403

    def test_wrong_password_returns_401(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client)
        _verify_email(auth_client, test_db)
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

    def test_email_case_insensitive_login(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        _register(auth_client, "myuser@example.com")
        _verify_email(auth_client, test_db, "myuser@example.com")
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
    def test_returns_new_access_token(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db)
        r = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_also_rotates_refresh_token(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db)
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

    def test_access_token_as_refresh_returns_401(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db)
        r = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert r.status_code == 401


# ── GET /auth/me ───────────────────────────────────────────────────────────────


class TestMe:
    def test_returns_user_data(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db, "me@example.com")
        r = auth_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "me@example.com"
        assert body["name"] == "Test User"
        assert body["is_active"] is True
        assert body["is_verified"] is True

    def test_response_has_required_fields(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db)
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

    def test_expired_token_returns_401(
        self, auth_client: TestClient, test_db: Session
    ) -> None:
        tokens = _full_register(auth_client, test_db)
        payload = jwt.decode(tokens["access_token"], _ACCESS_SECRET, algorithms=[_ALGORITHM])
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

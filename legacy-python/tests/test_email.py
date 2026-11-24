"""
Testes do módulo services/email — client, dev-fallback e templates.
Execute com: python -m pytest tests/test_email.py -v
"""
from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from services.email.client import EmailClient
from services.email.service import (
    _frontend_url,
    _load_template,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)


# ── EmailClient ────────────────────────────────────────────────────────────────


class TestEmailClientFromEnv:
    def test_returns_none_when_no_smtp_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        assert EmailClient.from_env() is None

    def test_returns_none_when_smtp_host_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "   ")
        assert EmailClient.from_env() is None

    def test_returns_client_when_smtp_host_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
        client = EmailClient.from_env()
        assert client is not None

    def test_from_header_with_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
        monkeypatch.setenv("SMTP_FROM_NAME", "Minha Empresa")
        client = EmailClient.from_env()
        assert client is not None
        assert "Minha Empresa" in client.from_header
        assert "noreply@example.com" in client.from_header

    def test_from_header_without_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
        monkeypatch.delenv("SMTP_FROM_NAME", raising=False)
        client = EmailClient.from_env()
        assert client is not None
        assert client.from_header == "noreply@example.com"


class TestEmailClientSend:
    def _make_client(self) -> EmailClient:
        return EmailClient(
            host="smtp.example.com",
            port=587,
            user="u",
            password="p",
            from_addr="noreply@example.com",
            from_name="Test",
            use_tls=True,
        )

    def test_send_calls_smtp_starttls(self) -> None:
        client = self._make_client()
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            client.send("to@example.com", "Subject", "text", "<p>html</p>")
        mock_smtp.__enter__.return_value.starttls.assert_called_once()

    def test_send_raises_on_smtp_error(self) -> None:
        client = self._make_client()
        mock_smtp = MagicMock()
        mock_smtp.__enter__.return_value.sendmail.side_effect = smtplib.SMTPException("fail")
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with pytest.raises(smtplib.SMTPException):
                client.send("to@example.com", "Subject", "text", "<p>html</p>")


# ── Dev fallback (no SMTP_HOST configured) ─────────────────────────────────────


class TestDevFallback:
    def test_send_verification_returns_false_without_smtp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        result = send_verification_email("Ana", "ana@example.com", "tok123")
        assert result is False

    def test_send_reset_returns_false_without_smtp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        result = send_password_reset_email("Ana", "ana@example.com", "tok456")
        assert result is False

    def test_send_welcome_returns_false_without_smtp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        result = send_welcome_email("Ana", "ana@example.com")
        assert result is False


# ── Template loading ───────────────────────────────────────────────────────────


class TestLoadTemplate:
    def test_verify_email_template_exists(self) -> None:
        html = _load_template("verify_email.html", name="Ana", link="http://example.com/verify")
        assert "Ana" in html
        assert "http://example.com/verify" in html

    def test_reset_password_template_exists(self) -> None:
        html = _load_template(
            "reset_password.html",
            name="Ana",
            link="http://example.com/reset",
            expire_text="30 minutos",
        )
        assert "Ana" in html
        assert "http://example.com/reset" in html
        assert "30 minutos" in html

    def test_welcome_template_exists(self) -> None:
        html = _load_template("welcome.html", name="Ana")
        assert "Ana" in html

    def test_missing_template_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            _load_template("nonexistent_template.html")


# ── Frontend URL helper ────────────────────────────────────────────────────────


class TestFrontendUrl:
    def test_uses_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FRONTEND_URL", "https://myapp.com/")
        assert _frontend_url() == "https://myapp.com"

    def test_defaults_to_localhost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        assert _frontend_url() == "http://localhost:8000"


# ── Link construction ──────────────────────────────────────────────────────────


class TestLinkConstruction:
    def test_verification_link_contains_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.setenv("FRONTEND_URL", "https://myapp.com")
        # Even though email won't send, we can verify the link is built correctly
        # by patching _send to capture args
        captured: list[str] = []

        def fake_send(to: str, subject: str, text_body: str, html_body: str) -> bool:
            captured.append(text_body)
            return True

        with patch("services.email.service._send", side_effect=fake_send):
            send_verification_email("Ana", "ana@example.com", "mytoken123")

        assert len(captured) == 1
        assert "mytoken123" in captured[0]
        assert "https://myapp.com" in captured[0]

    def test_reset_link_contains_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.setenv("FRONTEND_URL", "https://myapp.com")
        captured: list[str] = []

        def fake_send(to: str, subject: str, text_body: str, html_body: str) -> bool:
            captured.append(text_body)
            return True

        with patch("services.email.service._send", side_effect=fake_send):
            send_password_reset_email("Ana", "ana@example.com", "resettoken456")

        assert len(captured) == 1
        assert "resettoken456" in captured[0]
        assert "https://myapp.com" in captured[0]

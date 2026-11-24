from __future__ import annotations

import logging
import os
from pathlib import Path

from .client import EmailClient

_logger = logging.getLogger(__name__)
_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_template(template_name: str, **vars: str) -> str:
    tmpl = (_TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    for key, value in vars.items():
        tmpl = tmpl.replace(f"{{{{{key}}}}}", value)
    return tmpl


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:8000").rstrip("/")


def _send(to: str, subject: str, text_body: str, html_body: str) -> bool:
    client = EmailClient.from_env()
    if client is None:
        _logger.info(
            "SMTP not configured — skipping email | to=%s | subject=%s",
            to,
            subject,
        )
        return False
    try:
        client.send(to, subject, text_body, html_body)
        return True
    except Exception as exc:
        _logger.error(
            "Email send failed | to=%s | subject=%s | error=%s", to, subject, exc
        )
        return False


def send_verification_email(name: str, to_email: str, token: str) -> bool:
    link = f"{_frontend_url()}/?verify_token={token}"
    _logger.debug("Verification link | to=%s", to_email)
    html = _load_template("verify_email.html", name=name, link=link)
    text = (
        f"Olá {name},\n\n"
        "Confirme seu email clicando no link:\n"
        f"{link}\n\n"
        "O link expira em 24 horas.\n\n"
        "Caso não tenha criado uma conta, ignore este email."
    )
    return _send(to_email, "Confirme seu email — Império Caminhões", text, html)


def send_password_reset_email(name: str, to_email: str, token: str) -> bool:
    link = f"{_frontend_url()}/?reset_token={token}"
    _logger.debug("Password reset link | to=%s", to_email)
    expire_minutes = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
    expire_text = f"{expire_minutes} minutos"
    html = _load_template(
        "reset_password.html",
        name=name,
        link=link,
        expire_text=expire_text,
    )
    text = (
        f"Olá {name},\n\n"
        "Clique no link para redefinir sua senha:\n"
        f"{link}\n\n"
        f"O link expira em {expire_text}.\n\n"
        "Caso não tenha solicitado a redefinição, ignore este email com segurança."
    )
    return _send(to_email, "Redefinição de senha — Império Caminhões", text, html)


def send_welcome_email(name: str, to_email: str) -> bool:
    html = _load_template("welcome.html", name=name)
    text = (
        f"Olá {name},\n\n"
        "Sua conta foi confirmada com sucesso.\n\n"
        "Bem-vindo ao Império Caminhões!\n\n"
        "Acesse o sistema e comece a gerenciar suas campanhas de anúncios."
    )
    return _send(to_email, "Bem-vindo ao Império Caminhões!", text, html)

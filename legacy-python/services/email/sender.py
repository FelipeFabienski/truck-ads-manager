"""Kept as a compatibility stub — use services.email.service directly."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_logger = logging.getLogger(__name__)


def _smtp_host() -> str:
    return os.getenv("SMTP_HOST", "")


def send_verification_email(name: str, to_email: str, token: str) -> bool:
    """
    Send an email verification message.

    Returns True when the message was dispatched via SMTP.
    Returns False when SMTP is not configured — the verification link is
    written to the application log so developers can still test the flow
    without an email provider.
    """
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8000")
    link = f"{frontend_url}?verify_token={token}"

    if not _smtp_host():
        _logger.info(
            "SMTP not configured — verification link | to=%s | link=%s",
            to_email,
            link,
        )
        return False

    from_addr = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "noreply@example.com"))
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    text_body = (
        f"Olá {name},\n\n"
        "Confirme seu email clicando no link abaixo:\n"
        f"{link}\n\n"
        "O link expira em 24 horas.\n\n"
        "Caso não tenha criado uma conta, ignore este email."
    )
    html_body = f"""
    <html>
      <body style="font-family:sans-serif;color:#222;max-width:480px;margin:auto;padding:32px">
        <h2 style="color:#3b5bdb">Confirme seu email</h2>
        <p>Olá <strong>{name}</strong>,</p>
        <p>Clique no botão para ativar sua conta:</p>
        <p>
          <a href="{link}"
             style="background:#3b5bdb;color:#fff;padding:12px 28px;border-radius:8px;
                    text-decoration:none;display:inline-block;font-weight:600">
            Confirmar email
          </a>
        </p>
        <p style="color:#888;font-size:13px">
          Ou copie o link: <a href="{link}">{link}</a>
        </p>
        <p style="color:#888;font-size:13px">O link expira em 24&nbsp;horas.</p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Confirme seu email — Império Caminhões"
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(_smtp_host(), port) as smtp:
        if use_tls:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, to_email, msg.as_string())

    return True

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_logger = logging.getLogger(__name__)


class EmailClient:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        from_name: str,
        use_tls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from_addr = from_addr
        self._from_name = from_name
        self._use_tls = use_tls

    @property
    def from_header(self) -> str:
        if self._from_name:
            return f"{self._from_name} <{self._from_addr}>"
        return self._from_addr

    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        """Send an email via SMTP. Raises smtplib.SMTPException on failure."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_header
        msg["To"] = to
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._user and self._password:
                smtp.login(self._user, self._password)
            smtp.sendmail(self._from_addr, to, msg.as_string())

    @classmethod
    def from_env(cls) -> "EmailClient | None":
        """Returns None when SMTP_HOST is not configured."""
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            return None
        from_addr = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "noreply@example.com"))
        return cls(
            host=host,
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            from_addr=from_addr,
            from_name=os.getenv("SMTP_FROM_NAME", ""),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        )

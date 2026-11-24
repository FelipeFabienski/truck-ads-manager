from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import MetaAPIError, MetaAuthError, MetaRateLimitError

_API_VERSION = "v23.0"
_BASE_URL = f"https://graph.facebook.com/{_API_VERSION}"
_DEFAULT_TIMEOUT = 20.0

_AUTH_CODES = {190, 102}
_RATE_LIMIT_CODES = {4, 17, 32, 613}

logger = logging.getLogger(__name__)


def _raise_for_meta_error(response: httpx.Response, context: str = "") -> None:
    if response.is_success:
        return
    try:
        body = response.json()
    except Exception:
        response.raise_for_status()
        return
    error = body.get("error", {})
    code: int = error.get("code", 0)
    subcode: int | None = error.get("error_subcode")
    message: str = error.get("message", "Unknown Meta API error")
    if context:
        message = f"[{context}] {message}"
    logger.error("Meta API error %s/%s: %s", code, subcode, message)
    if code in _AUTH_CODES:
        raise MetaAuthError(message, code, subcode)
    if code in _RATE_LIMIT_CODES:
        raise MetaRateLimitError(message, code, subcode)
    raise MetaAPIError(message, code, subcode)


class MetaAPIClient:
    """
    Synchronous httpx client for Meta Graph API v23.0.

    Retries automatically on rate-limit errors (tenacity exponential backoff).
    Token is passed via Authorization header; also appended to payloads per Meta's spec.
    """

    def __init__(
        self,
        access_token: str,
        ad_account_id: str,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._token = access_token
        self._account_id = ad_account_id
        self._account_prefix = f"act_{ad_account_id}"
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=timeout,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MetaAPIClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type(MetaRateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def get(self, path: str, params: dict | None = None) -> dict:
        params = {**(params or {}), "access_token": self._token}
        logger.debug("GET /%s", path)
        r = self._client.get(f"/{path}", params=params)
        _raise_for_meta_error(r, f"GET /{path}")
        return r.json()

    @retry(
        retry=retry_if_exception_type(MetaRateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def post(self, path: str, payload: dict) -> dict:
        logger.debug("POST /%s", path)
        r = self._client.post(f"/{path}", json={**payload, "access_token": self._token})
        _raise_for_meta_error(r, f"POST /{path}")
        return r.json()

    @retry(
        retry=retry_if_exception_type(MetaRateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def post_multipart(self, path: str, data: dict, files: dict) -> dict:
        """POST multipart/form-data — used for image uploads."""
        logger.debug("POST multipart /%s", path)
        r = self._client.post(
            f"/{path}",
            data={**data, "access_token": self._token},
            files=files,
        )
        _raise_for_meta_error(r, f"POST multipart /{path}")
        return r.json()

    @retry(
        retry=retry_if_exception_type(MetaRateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def patch(self, path: str, payload: dict) -> dict:
        """Update via POST — Meta uses POST for all mutations."""
        logger.debug("PATCH /%s", path)
        r = self._client.post(f"/{path}", json={**payload, "access_token": self._token})
        _raise_for_meta_error(r, f"PATCH /{path}")
        return r.json()

    @property
    def account_path(self) -> str:
        return self._account_prefix

    def validate_connection(self) -> bool:
        """Verify token + account access by pinging the account endpoint."""
        from ads.exceptions import InvalidAccount
        result = self.get(self._account_prefix, {"fields": "id,name,account_status"})
        if result.get("account_status") != 1:
            raise InvalidAccount(self._account_id)
        return True

from __future__ import annotations

import logging

import httpx

_API_VERSION = "v23.0"
_BASE_URL = f"https://graph.facebook.com/{_API_VERSION}"
_TIMEOUT = 15.0

logger = logging.getLogger(__name__)


class MetaTokenError(Exception):
    """Raised when token is invalid, expired, or lacks required permissions."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def normalize_ad_account_id(raw: str) -> str:
    """Ensure the ad account ID is in act_<numeric_id> format.

    Accepts "123456789" or "act_123456789" — never produces "act_act_...".
    """
    stripped = raw.strip()
    numeric = stripped
    while numeric.startswith("act_"):
        numeric = numeric[4:]
    if not numeric:
        raise ValueError(f"ad_account_id inválido: '{raw}'")
    return f"act_{numeric}"


def validate_meta_token(access_token: str) -> dict:
    """
    Validate token via GET /me. Returns {"id": ..., "name": ...}.
    Raises MetaTokenError if token is invalid or expired.
    """
    try:
        r = httpx.get(
            f"{_BASE_URL}/me",
            params={"access_token": access_token, "fields": "id,name"},
            timeout=_TIMEOUT,
        )
    except httpx.TimeoutException:
        raise MetaTokenError("Timeout ao validar token Meta. Tente novamente.", 400)
    except httpx.RequestError as exc:
        raise MetaTokenError(f"Erro de conexão ao validar token: {exc}", 400)

    if not r.is_success:
        err = _parse_error(r)
        code = err.get("code", 0)
        msg = err.get("message", "Token Meta inválido")
        logger.warning("Meta token validation failed — code=%s", code)
        if code in (190, 102):
            raise MetaTokenError("Token Meta inválido ou expirado.", 400)
        raise MetaTokenError(f"Erro ao validar token Meta: {msg}", 400)

    return r.json()


def validate_ad_account(access_token: str, ad_account_id: str) -> dict:
    """
    Validate the ad account exists and is accessible.
    Raises MetaTokenError if account is invalid or token lacks permission.
    """
    account_path = normalize_ad_account_id(ad_account_id)
    try:
        r = httpx.get(
            f"{_BASE_URL}/{account_path}",
            params={
                "access_token": access_token,
                "fields": "id,name,account_status,currency",
            },
            timeout=_TIMEOUT,
        )
    except httpx.TimeoutException:
        raise MetaTokenError("Timeout ao validar conta de anúncios.", 400)
    except httpx.RequestError as exc:
        raise MetaTokenError(f"Erro de conexão ao validar conta de anúncios: {exc}", 400)

    if not r.is_success:
        err = _parse_error(r)
        code = err.get("code", 0)
        msg = err.get("message", "Conta de anúncios não encontrada ou inacessível")
        logger.warning("Meta ad account validation failed — code=%s account=%s", code, account_path)
        if code in (10, 200, 273):
            raise MetaTokenError(
                "Token sem permissão para acessar essa conta de anúncios. "
                "Verifique se ads_management e ads_read estão habilitados.",
                403,
            )
        raise MetaTokenError(f"Conta de anúncios inválida: {msg}", 400)

    return r.json()


def validate_page(access_token: str, page_id: str) -> dict:
    """
    Validate the Facebook Page exists and is accessible.
    Raises MetaTokenError if page is invalid or inaccessible.
    """
    try:
        r = httpx.get(
            f"{_BASE_URL}/{page_id}",
            params={"access_token": access_token, "fields": "id,name,category"},
            timeout=_TIMEOUT,
        )
    except httpx.TimeoutException:
        raise MetaTokenError("Timeout ao validar página.", 400)
    except httpx.RequestError as exc:
        raise MetaTokenError(f"Erro de conexão ao validar página: {exc}", 400)

    if not r.is_success:
        err = _parse_error(r)
        msg = err.get("message", "Página não encontrada ou inacessível")
        logger.warning("Meta page validation failed — page_id=%s", page_id)
        raise MetaTokenError(f"Página inválida: {msg}", 400)

    return r.json()


def _parse_error(response: httpx.Response) -> dict:
    try:
        return response.json().get("error", {})
    except Exception:
        return {}

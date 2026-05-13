from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

ALGORITHM = "HS256"

_DEV_ACCESS_SECRET = "dev-jwt-secret-change-in-production"
_DEV_REFRESH_SECRET = "dev-refresh-secret-change-in-production"


def _access_secret() -> str:
    return os.getenv("JWT_SECRET_KEY", _DEV_ACCESS_SECRET)


def _refresh_secret() -> str:
    return os.getenv("JWT_REFRESH_SECRET_KEY", _DEV_REFRESH_SECRET)


def _access_expire_minutes() -> int:
    return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))


def _refresh_expire_days() -> int:
    return int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_access_expire_minutes()),
    }
    return jwt.encode(payload, _access_secret(), algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=_refresh_expire_days()),
    }
    return jwt.encode(payload, _refresh_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, _access_secret(), algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("not an access token")
    return int(payload["sub"])


def decode_refresh_token(token: str) -> int:
    payload = jwt.decode(token, _refresh_secret(), algorithms=[ALGORITHM])
    if payload.get("type") != "refresh":
        raise JWTError("not a refresh token")
    return int(payload["sub"])

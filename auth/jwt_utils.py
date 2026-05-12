from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

ALGORITHM = "HS256"
_EXPIRY_DAYS = 7
_DEV_SECRET = "dev-jwt-secret-change-in-production"


def _secret() -> str:
    return os.getenv("JWT_SECRET_KEY", _DEV_SECRET)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=_EXPIRY_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    return int(payload["sub"])

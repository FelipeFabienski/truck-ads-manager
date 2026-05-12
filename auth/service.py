from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from db.models.meta_account import MetaAdAccount
from db.models.user import User

from .crypto import encrypt

FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID", "")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")
FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI", "")
_GRAPH = "https://graph.facebook.com/v23.0"
_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", "dev-state-secret-change-me")

_SCOPES = ",".join([
    "email",
    "pages_show_list",
    "ads_management",
    "ads_read",
    "business_management",
    "leads_retrieval",
    "whatsapp_business_management",
    "pages_read_engagement",
    "whatsapp_business_messaging",
])


# ── CSRF state ─────────────────────────────────────────────────────────────────

def generate_state() -> str:
    nonce = secrets.token_hex(16)
    sig = hmac.new(_STATE_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def verify_state(state: str) -> bool:
    try:
        nonce, sig = state.split(".", 1)
        expected = hmac.new(_STATE_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


# ── OAuth URLs ─────────────────────────────────────────────────────────────────

def build_oauth_url(state: str) -> str:
    from urllib.parse import quote
    return (
        f"https://www.facebook.com/v23.0/dialog/oauth"
        f"?client_id={FACEBOOK_APP_ID}"
        f"&redirect_uri={quote(FACEBOOK_REDIRECT_URI, safe='')}"
        f"&scope={_SCOPES}"
        f"&state={state}"
        f"&response_type=code"
    )


# ── Graph API calls ────────────────────────────────────────────────────────────

def exchange_code(code: str) -> dict:
    r = httpx.get(f"{_GRAPH}/oauth/access_token", params={
        "client_id": FACEBOOK_APP_ID,
        "client_secret": FACEBOOK_APP_SECRET,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "code": code,
    }, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_user_profile(access_token: str) -> dict:
    r = httpx.get(f"{_GRAPH}/me", params={
        "fields": "id,name,email",
        "access_token": access_token,
    }, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_ad_accounts(access_token: str) -> list[dict]:
    r = httpx.get(f"{_GRAPH}/me/adaccounts", params={
        "fields": "id,name,currency,account_status",
        "access_token": access_token,
        "limit": 50,
    }, timeout=15)
    r.raise_for_status()
    return r.json().get("data", [])


# ── DB operations ─────────────────────────────────────────────────────────────

def upsert_user(db: Session, profile: dict, token_data: dict) -> User:
    fb_id = profile["id"]
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 0)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        if expires_in else None
    )

    user = db.query(User).filter_by(facebook_user_id=fb_id).first()
    if user:
        user.access_token_enc = encrypt(access_token)
        user.token_expires_at = expires_at
        user.name = profile.get("name", user.name)
        user.email = profile.get("email", user.email)
    else:
        user = User(
            facebook_user_id=fb_id,
            name=profile.get("name", ""),
            email=profile.get("email"),
            access_token_enc=encrypt(access_token),
            token_expires_at=expires_at,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


def sync_ad_accounts(db: Session, user: User, access_token: str) -> list[MetaAdAccount]:
    accounts_data = fetch_ad_accounts(access_token)

    db.query(MetaAdAccount).filter_by(user_id=user.id).delete()

    result: list[MetaAdAccount] = []
    for acc in accounts_data:
        ma = MetaAdAccount(
            user_id=user.id,
            ad_account_id=acc["id"],
            account_name=acc.get("name"),
            currency=acc.get("currency"),
            account_status=acc.get("account_status"),
        )
        db.add(ma)
        result.append(ma)

    db.commit()

    if not user.active_ad_account_id and result:
        user.active_ad_account_id = result[0].ad_account_id
        db.commit()

    return result

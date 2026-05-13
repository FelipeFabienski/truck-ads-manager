from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db.models.user import User

from .password import hash_password, verify_password


def _verification_expire_hours() -> int:
    return int(os.getenv("EMAIL_VERIFICATION_EXPIRE_HOURS", "24"))


def _generate_verification_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=_verification_expire_hours())
    return token, expires


def register_user(db: Session, name: str, email: str, plain_password: str) -> User:
    email = email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado",
        )
    token, expires = _generate_verification_token()
    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(plain_password),
        is_active=True,
        is_verified=False,
        email_verification_token=token,
        email_verification_expires_at=expires,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def verify_email_token(db: Session, token: str) -> User:
    user = db.query(User).filter_by(email_verification_token=token).first()
    # Use the same error for unknown and expired tokens to avoid user enumeration
    _invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Token de verificação inválido ou expirado",
    )
    if not user:
        raise _invalid

    expires_at = user.email_verification_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is None or expires_at < datetime.now(timezone.utc):
        raise _invalid

    user.is_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, plain_password: str) -> User:
    email = email.lower().strip()
    user = db.query(User).filter_by(email=email).first()
    if not user or not verify_password(plain_password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada",
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirme seu email antes de fazer login",
        )
    return user

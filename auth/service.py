from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db.models.user import User

from .password import hash_password, verify_password


def register_user(db: Session, name: str, email: str, plain_password: str) -> User:
    email = email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado",
        )
    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(plain_password),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
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
    return user

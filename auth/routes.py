from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from db.database import get_db
from db.models.user import User

from . import service
from .dependencies import get_current_user
from .jwt_utils import create_access_token, create_refresh_token, decode_refresh_token
from .schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Registrar novo usuário",
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = service.register_user(db, body.name, str(body.email), body.password)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autenticar com e-mail e senha",
)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = service.authenticate_user(db, str(body.email), body.password)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token via refresh token",
)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user_id = decode_refresh_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        )
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo",
        )
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/logout", summary="Encerrar sessão")
def logout() -> dict[str, bool]:
    return {"ok": True}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Dados do usuário autenticado",
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

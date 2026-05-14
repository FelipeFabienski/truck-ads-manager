from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import JWTError
from sqlalchemy.orm import Session

from db.database import get_db
from db.models.user import User
from services.email import send_password_reset_email, send_verification_email, send_welcome_email

from . import service
from .dependencies import get_current_user
from .jwt_utils import create_access_token, create_refresh_token, decode_refresh_token
from .schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResendVerificationRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    summary="Registrar novo usuário",
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    user = service.register_user(db, body.name, str(body.email), body.password)
    token = user.email_verification_token or ""
    email_sent = send_verification_email(user.name, user.email, token)
    return RegisterResponse(email=user.email, email_sent=email_sent)


@router.get(
    "/verify-email",
    summary="Confirmar email via token",
    responses={
        200: {"description": "Email confirmado com sucesso"},
        400: {"description": "Token inválido ou expirado"},
    },
)
def verify_email(
    token: str = Query(..., description="Token de verificação recebido por email"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = service.verify_email_token(db, token)
    send_welcome_email(user.name, user.email)
    return {"verified": True, "message": "Email confirmado com sucesso. Faça login para continuar."}


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


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Reenviar email de verificação",
)
def resend_verification(
    body: ResendVerificationRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    _GENERIC = "Se o email estiver cadastrado e ainda não estiver verificado, enviaremos uma nova confirmação."
    result = service.resend_verification(db, str(body.email))
    if result is not None:
        name, token = result
        send_verification_email(name, str(body.email), token)
    return MessageResponse(message=_GENERIC)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Solicitar redefinição de senha",
)
def forgot_password(
    body: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    _GENERIC = "Se o email estiver cadastrado, enviaremos instruções para redefinir a senha."
    result = service.request_password_reset(db, str(body.email))
    if result is not None:
        name, token = result
        send_password_reset_email(name, str(body.email), token)
    return MessageResponse(message=_GENERIC)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Redefinir senha via token",
    responses={400: {"description": "Token inválido ou expirado"}},
)
def reset_password(
    body: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    service.reset_password(db, body.token, body.new_password)
    return MessageResponse(message="Senha atualizada com sucesso.")


@router.post("/logout", summary="Encerrar sessão")
def logout() -> dict[str, bool]:
    # Tokens are invalidated client-side by clearing localStorage.
    # TODO: implement server-side refresh token blacklist for full revocation.
    return {"ok": True}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Dados do usuário autenticado",
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

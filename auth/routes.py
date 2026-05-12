from __future__ import annotations

from fastapi import APIRouter, Depends

from db.models.user import User

from .dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/logout", summary="Encerrar sessão")
def logout() -> dict:
    return {"ok": True}


@router.get("/me", summary="Dados do usuário autenticado")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "active_ad_account_id": current_user.active_ad_account_id,
    }

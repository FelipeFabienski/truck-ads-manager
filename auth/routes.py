from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.database import get_db
from db.models.meta_account import MetaAdAccount
from db.models.user import User

from . import service
from .dependencies import get_current_user
from .jwt_utils import create_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/facebook/login", summary="Iniciar login via Facebook OAuth")
def facebook_login() -> RedirectResponse:
    state = service.generate_state()
    url = service.build_oauth_url(state)
    return RedirectResponse(url)


@router.get("/facebook/callback", include_in_schema=False)
def facebook_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not service.verify_state(state):
        raise HTTPException(status_code=400, detail="State OAuth inválido")
    if not service.FACEBOOK_APP_ID:
        raise HTTPException(status_code=503, detail="Facebook OAuth não configurado")

    token_data = service.exchange_code(code)
    access_token = token_data["access_token"]
    profile = service.fetch_user_profile(access_token)

    user = service.upsert_user(db, profile, token_data)
    service.sync_ad_accounts(db, user, access_token)

    jwt = create_token(user.id)
    return RedirectResponse(f"/?token={jwt}")


@router.post("/logout", summary="Encerrar sessão")
def logout() -> dict:
    return {"ok": True}


@router.get("/me", summary="Dados do usuário autenticado")
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    accounts = db.query(MetaAdAccount).filter_by(user_id=current_user.id).all()
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "facebook_user_id": current_user.facebook_user_id,
        "active_ad_account_id": current_user.active_ad_account_id,
        "ad_accounts": [
            {
                "id": a.ad_account_id,
                "name": a.account_name,
                "currency": a.currency,
                "status": a.account_status,
            }
            for a in accounts
        ],
    }


@router.patch("/me/account", summary="Selecionar conta de anúncios ativa")
def select_account(
    ad_account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    acc = (
        db.query(MetaAdAccount)
        .filter_by(user_id=current_user.id, ad_account_id=ad_account_id)
        .first()
    )
    if not acc:
        raise HTTPException(status_code=404, detail="Conta não encontrada para este usuário")
    current_user.active_ad_account_id = ad_account_id
    db.commit()
    return {"active_ad_account_id": ad_account_id}

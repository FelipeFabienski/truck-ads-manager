from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ads.factory import get_ads_provider
from ads.providers.meta import MetaAdsProvider
from ads.truck.service import TruckAdService
from auth.crypto import decrypt
from auth.dependencies import get_current_user
from db.database import get_db
from db.models.user import User
from db.repository import CampaignRepository


def get_truck_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TruckAdService:
    """
    Cria TruckAdService com provider e repositório vinculados ao usuário autenticado.

    - Se o usuário tem active_ad_account_id → MetaAdsProvider com token do usuário.
    - Caso contrário → MockAdsProvider (conta sem conta Meta vinculada).
    - CampaignRepository filtra campanhas apenas do usuário autenticado.
    """
    ad_account_id = current_user.active_ad_account_id

    if ad_account_id:
        access_token = decrypt(current_user.access_token_enc)
        clean_id = ad_account_id.replace("act_", "")
        provider = MetaAdsProvider(access_token=access_token, ad_account_id=clean_id)
    else:
        provider = get_ads_provider("mock")

    return TruckAdService(
        provider=provider,
        repository=CampaignRepository(db, user_id=current_user.id),
    )

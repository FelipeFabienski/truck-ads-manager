from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.orm import Session

from ads.factory import get_ads_provider
from ads.truck.service import TruckAdService
from db.database import get_db
from db.repository import CampaignRepository


def get_truck_service(db: Session = Depends(get_db)) -> TruckAdService:
    """Dependência FastAPI — instância por request com sessão DB injetada.

    ADS_PROVIDER=mock   (padrão) — MockAdsProvider + PostgreSQL
    ADS_PROVIDER=demo           — igual ao mock (dados demo via seed no banco)
    ADS_PROVIDER=meta           — Meta Ads real (requer META_ACCESS_TOKEN
                                  e META_AD_ACCOUNT_ID no ambiente)
    """
    provider_name = os.getenv("ADS_PROVIDER", "mock")

    if provider_name == "meta":
        provider = get_ads_provider(
            "meta",
            access_token=os.environ["META_ACCESS_TOKEN"],
            ad_account_id=os.environ["META_AD_ACCOUNT_ID"],
        )
    else:
        provider = get_ads_provider("mock")

    return TruckAdService(
        provider=provider,
        repository=CampaignRepository(db),
    )

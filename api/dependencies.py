from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ads.factory import get_ads_provider
from ads.truck.service import TruckAdService
from auth.dependencies import get_current_user
from db.database import get_db
from db.models.user import User
from db.repository import CampaignRepository


def get_truck_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TruckAdService:
    provider = get_ads_provider("mock")
    return TruckAdService(
        provider=provider,
        repository=CampaignRepository(db, user_id=current_user.id),
    )

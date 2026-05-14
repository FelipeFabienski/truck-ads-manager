from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.orm import Session

from ads.factory import get_ads_provider
from ads.truck.ai_generator import AIGeneratorService, ClaudeAIGenerator, MockAIGenerator
from ads.truck.service import TruckAdService
from auth.dependencies import get_current_user
from db.database import get_db
from db.models.user import User
from db.repository import CampaignRepository


def _get_ai_generator() -> AIGeneratorService:
    name = os.getenv("AI_GENERATOR", "mock").strip().lower()
    if name == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "AI_GENERATOR=claude requires ANTHROPIC_API_KEY to be set."
            )
        return ClaudeAIGenerator(api_key=api_key)
    return MockAIGenerator()


def get_truck_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TruckAdService:
    provider_name = os.getenv("ADS_PROVIDER", "mock").strip().lower()
    return TruckAdService(
        provider=get_ads_provider(provider_name),
        ai_generator=_get_ai_generator(),
        repository=CampaignRepository(db, user_id=current_user.id),
    )

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.orm import Session

from ads.factory import get_ads_provider
from ads.truck.ai_generator import AIGeneratorService, ClaudeAIGenerator
from ads.truck.template_generator import TemplateAdGenerator
from ads.truck.service import TruckAdService
from auth.dependencies import get_current_user
from db.database import get_db
from db.models.user import User
from db.repository import CampaignRepository


def _get_ai_generator() -> AIGeneratorService:
    if os.getenv("ENABLE_AI_COPY", "false").strip().lower() != "true":
        return TemplateAdGenerator()

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        import logging
        logging.getLogger(__name__).warning(
            "ENABLE_AI_COPY=true mas ANTHROPIC_API_KEY não configurada — "
            "usando TemplateAdGenerator como fallback."
        )
        return TemplateAdGenerator()

    return ClaudeAIGenerator(api_key=api_key)


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

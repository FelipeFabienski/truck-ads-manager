from __future__ import annotations

import os
from functools import lru_cache

from ads.truck.service import TruckAdService


@lru_cache(maxsize=1)
def _build_service() -> TruckAdService:
    """
    Instância singleton do TruckAdService.
    Lê ADS_PROVIDER do ambiente para escolher o provider:

        ADS_PROVIDER=mock   (padrão) — in-memory, sem dados pré-carregados
        ADS_PROVIDER=demo           — in-memory com 3 caminhões de exemplo
        ADS_PROVIDER=meta           — API real da Meta (requer META_ACCESS_TOKEN
                                      e META_AD_ACCOUNT_ID no ambiente)
    """
    provider_name = os.getenv("ADS_PROVIDER", "mock")

    if provider_name == "meta":
        return TruckAdService.with_meta(
            access_token=os.environ["META_ACCESS_TOKEN"],
            ad_account_id=os.environ["META_AD_ACCOUNT_ID"],
        )

    if provider_name == "demo":
        from ads.providers.mock_provider import MockAdsProvider
        from ads.truck.ai_generator import MockAIGenerator

        return TruckAdService(
            provider=MockAdsProvider.with_demo_data(),
            ai_generator=MockAIGenerator(),
        )

    return TruckAdService.with_mock()


def get_truck_service() -> TruckAdService:
    """FastAPI dependency — injeta o TruckAdService nos endpoints."""
    return _build_service()

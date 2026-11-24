from .exceptions import (
    AdsError,
    AdNotFound,
    AdSetNotFound,
    CampaignNotFound,
    CreationError,
    InvalidAccount,
    InvalidTransition,
)
from .factory import clear_registry, get_ads_provider
from .models import Ad, AdSet, Audience, Campaign, CampaignObjective, CampaignStatus, Creative, Metrics
from .provider import AdsProvider
from .service import AdService
from .truck import (
    AIGeneratedContent,
    AIGeneratorService,
    ClaudeAIGenerator,
    MockAIGenerator,
    TruckAdCreateRequest,
    TruckAdPublishResponse,
    TruckAdService,
    to_frontend_dto,
    translate_status_to_en,
    translate_status_to_pt,
)

__all__ = [
    # Interface
    "AdsProvider",
    # Services
    "AdService",
    "TruckAdService",
    # Truck schemas
    "TruckAdCreateRequest",
    "TruckAdPublishResponse",
    "AIGeneratedContent",
    # AI generators
    "AIGeneratorService",
    "MockAIGenerator",
    "ClaudeAIGenerator",
    # Adapter
    "to_frontend_dto",
    "translate_status_to_pt",
    "translate_status_to_en",
    # Factory
    "get_ads_provider",
    "clear_registry",
    # Models
    "Campaign",
    "CampaignStatus",
    "CampaignObjective",
    "AdSet",
    "Audience",
    "Ad",
    "Creative",
    "Metrics",
    # Exceptions
    "AdsError",
    "CampaignNotFound",
    "AdSetNotFound",
    "AdNotFound",
    "InvalidAccount",
    "CreationError",
    "InvalidTransition",
]

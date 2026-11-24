from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"


class CampaignObjective(str, Enum):
    AWARENESS = "OUTCOME_AWARENESS"
    TRAFFIC = "OUTCOME_TRAFFIC"
    ENGAGEMENT = "OUTCOME_ENGAGEMENT"
    LEADS = "OUTCOME_LEADS"
    SALES = "OUTCOME_SALES"


@dataclass
class Campaign:
    id: str
    name: str
    objective: str
    status: CampaignStatus
    budget: float
    created_at: datetime
    updated_at: datetime | None = None
    meta_id: str | None = None
    extra: dict = field(default_factory=dict)  # domain-specific metadata (truck info, etc.)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "objective": self.objective,
            "status": self.status.value if isinstance(self.status, CampaignStatus) else self.status,
            "budget": self.budget,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "meta_id": self.meta_id,
            "extra": self.extra,
        }


@dataclass
class Audience:
    locations: list[str]
    age_min: int
    age_max: int
    interests: list[str]
    gender: str = "all"

    def to_dict(self) -> dict:
        return {
            "locations": self.locations,
            "age_min": self.age_min,
            "age_max": self.age_max,
            "interests": self.interests,
            "gender": self.gender,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Audience":
        return cls(
            locations=data.get("locations", ["BR"]),
            age_min=data.get("age_min", 18),
            age_max=data.get("age_max", 65),
            interests=data.get("interests", []),
            gender=data.get("gender", "all"),
        )


@dataclass
class AdSet:
    id: str
    campaign_id: str
    name: str
    audience: Audience
    budget: float
    schedule: dict
    status: CampaignStatus = CampaignStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    meta_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "audience": (
                self.audience.to_dict()
                if isinstance(self.audience, Audience)
                else self.audience
            ),
            "budget": self.budget,
            "schedule": self.schedule,
            "status": (
                self.status.value if isinstance(self.status, CampaignStatus) else self.status
            ),
            "created_at": self.created_at.isoformat(),
            "meta_id": self.meta_id,
        }


@dataclass
class Creative:
    type: str  # "image" | "video"
    url: str
    caption: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "url": self.url, "caption": self.caption}

    @classmethod
    def from_dict(cls, data: dict) -> "Creative":
        return cls(
            type=data.get("type", "image"),
            url=data.get("url", ""),
            caption=data.get("caption", ""),
        )


@dataclass
class Ad:
    id: str
    campaign_id: str
    adset_id: str
    name: str
    copy: str
    headline: str
    creative: Creative
    destination: str
    status: CampaignStatus = CampaignStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    meta_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "name": self.name,
            "copy": self.copy,
            "headline": self.headline,
            "creative": (
                self.creative.to_dict()
                if isinstance(self.creative, Creative)
                else self.creative
            ),
            "destination": self.destination,
            "status": (
                self.status.value if isinstance(self.status, CampaignStatus) else self.status
            ),
            "created_at": self.created_at.isoformat(),
            "meta_id": self.meta_id,
        }


@dataclass
class Metrics:
    campaign_id: str
    impressions: int
    clicks: int
    leads: int
    spent: float
    cpl: float
    period: str = "last_7d"

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "leads": self.leads,
            "spent": self.spent,
            "cpl": self.cpl,
            "period": self.period,
        }

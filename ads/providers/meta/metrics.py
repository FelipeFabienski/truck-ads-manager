from __future__ import annotations

from datetime import datetime, timezone

from .client import MetaAPIClient

_PERIOD_MAP: dict[str, str] = {
    "today": "today",
    "last_7d": "last_7_days",
    "last_30d": "last_30_days",
}

_LEAD_ACTION_TYPES = frozenset({
    "lead",
    "onsite_conversion.lead_grouped",
    "offsite_conversion.fb_pixel_lead",
    "leadgen_grouped",
    "messaging_conversation_started_7d",
    "whatsapp_conversation_started",
})


def get_campaign_insights(client: MetaAPIClient, campaign_id: str, period: str = "last_7d") -> dict:
    params = {
        "fields": "impressions,reach,clicks,spend,cpc,cpm,ctr,actions",
        "date_preset": _PERIOD_MAP.get(period, "last_7_days"),
        "level": "campaign",
    }
    result = client.get(f"{campaign_id}/insights", params)
    row = result.get("data", [{}])[0] if result.get("data") else {}

    actions = {a["action_type"]: int(float(a["value"])) for a in row.get("actions", [])}
    leads = sum(actions.get(t, 0) for t in _LEAD_ACTION_TYPES)
    spent = float(row.get("spend", 0))

    def _opt_float(key: str) -> float | None:
        val = row.get(key)
        return float(val) if val else None

    return {
        "campaign_id": campaign_id,
        "impressions": int(row.get("impressions", 0)),
        "reach": int(row.get("reach", 0)),
        "clicks": int(row.get("clicks", 0)),
        "leads": leads,
        "spent": spent,
        "cpl": round(spent / leads, 2) if leads else None,
        "cpc": _opt_float("cpc"),
        "cpm": _opt_float("cpm"),
        "ctr": _opt_float("ctr"),
        "source": "meta",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
    }


def get_metrics(client: MetaAPIClient, campaign_id: str, period: str = "last_7d") -> dict:
    return get_campaign_insights(client, campaign_id, period)


def sync_metrics(client: MetaAPIClient, campaign_id: str) -> dict:
    return get_campaign_insights(client, campaign_id, "last_30d")

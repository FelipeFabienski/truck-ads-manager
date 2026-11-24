from __future__ import annotations

from .client import MetaAPIClient

_PERIOD_MAP: dict[str, str] = {
    "today": "today",
    "last_7d": "last_7_days",
    "last_30d": "last_30_days",
}


def get_metrics(client: MetaAPIClient, campaign_id: str, period: str = "last_7d") -> dict:
    params = {
        "fields": "impressions,clicks,spend,actions",
        "date_preset": _PERIOD_MAP.get(period, "last_7_days"),
        "level": "campaign",
    }
    result = client.get(f"{campaign_id}/insights", params)
    row = result.get("data", [{}])[0] if result.get("data") else {}

    actions = {a["action_type"]: int(float(a["value"])) for a in row.get("actions", [])}
    leads = actions.get("lead", 0) + actions.get("onsite_conversion.lead_grouped", 0)
    spent = float(row.get("spend", 0))

    return {
        "campaign_id": campaign_id,
        "impressions": int(row.get("impressions", 0)),
        "clicks": int(row.get("clicks", 0)),
        "leads": leads,
        "spent": spent,
        "cpl": round(spent / leads, 2) if leads else 0.0,
        "period": period,
    }


def sync_metrics(client: MetaAPIClient, campaign_id: str) -> dict:
    """Fetch last-30d metrics snapshot for a campaign."""
    return get_metrics(client, campaign_id, "last_30d")

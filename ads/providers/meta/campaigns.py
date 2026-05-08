from __future__ import annotations

from .client import MetaAPIClient

_STATUS_MAP: dict[str, str] = {
    "ACTIVE": "active",
    "PAUSED": "paused",
    "DELETED": "deleted",
    "ARCHIVED": "paused",
}


def create_campaign(client: MetaAPIClient, data: dict) -> dict:
    payload: dict = {
        "name": data["name"],
        "objective": data.get("objective", "OUTCOME_LEADS"),
        "status": "PAUSED",
        "special_ad_categories": data.get("special_ad_categories", []),
    }
    if budget := data.get("budget"):
        payload["daily_budget"] = int(float(budget) * 100)

    result = client.post(f"{client.account_path}/campaigns", payload)
    return {
        "id": result["id"],
        "name": data["name"],
        "objective": payload["objective"],
        "status": "draft",
        "budget": data.get("budget", 0),
        "created_at": None,
        "meta_id": result["id"],
    }


def update_campaign(client: MetaAPIClient, campaign_id: str, data: dict) -> dict:
    allowed = {"name", "status", "daily_budget", "objective"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "budget" in data and "daily_budget" not in payload:
        payload["daily_budget"] = int(float(data["budget"]) * 100)
    client.patch(campaign_id, payload)
    return {"id": campaign_id, **data}


def get_campaign(client: MetaAPIClient, campaign_id: str) -> dict:
    result = client.get(
        campaign_id,
        {"fields": "id,name,objective,status,daily_budget,created_time"},
    )
    return {
        "id": result["id"],
        "name": result.get("name"),
        "objective": result.get("objective"),
        "status": _STATUS_MAP.get(result.get("status", ""), "draft"),
        "budget": int(result.get("daily_budget", 0)) / 100,
        "created_at": result.get("created_time"),
        "meta_id": result["id"],
    }


def list_campaigns(client: MetaAPIClient, filters: dict | None = None) -> list[dict]:
    params: dict = {"fields": "id,name,objective,status,daily_budget,created_time"}
    if filters and "status" in filters:
        params["effective_status"] = [filters["status"].upper()]

    result = client.get(f"{client.account_path}/campaigns", params)
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "objective": c.get("objective"),
            "status": _STATUS_MAP.get(c.get("status", ""), "draft"),
            "budget": int(c.get("daily_budget", 0)) / 100,
            "created_at": c.get("created_time"),
            "meta_id": c["id"],
        }
        for c in result.get("data", [])
    ]


def delete_campaign(client: MetaAPIClient, campaign_id: str) -> dict:
    client.patch(campaign_id, {"status": "DELETED"})
    return {"deleted": True, "campaign_id": campaign_id}

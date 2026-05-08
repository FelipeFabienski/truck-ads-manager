from __future__ import annotations

from .client import MetaAPIClient


def create_adset(client: MetaAPIClient, data: dict) -> dict:
    audience = data.get("audience", {})

    targeting: dict = {
        "geo_locations": {"countries": ["BR"]},
        "age_min": audience.get("age_min", 18),
        "age_max": audience.get("age_max", 65),
    }

    if interests := audience.get("interests"):
        targeting["flexible_spec"] = [{"interests": [{"name": i} for i in interests]}]

    gender = audience.get("gender", "all")
    if gender == "male":
        targeting["genders"] = [1]
    elif gender == "female":
        targeting["genders"] = [2]

    placements: list[str] = data.get("placements", ["feed"])
    publisher_platforms: list[str] = []
    facebook_positions: list[str] = []
    instagram_positions: list[str] = []

    for p in placements:
        if p == "feed":
            publisher_platforms += ["facebook", "instagram"]
            facebook_positions.append("feed")
            instagram_positions.append("stream")
        elif p == "reels":
            publisher_platforms += ["facebook", "instagram"]
            facebook_positions.append("facebook_reels")
            instagram_positions.append("reels")
        elif p == "stories":
            publisher_platforms += ["facebook", "instagram"]
            facebook_positions.append("story")
            instagram_positions.append("story")
        elif p == "marketplace":
            publisher_platforms.append("facebook")
            facebook_positions.append("marketplace")

    if publisher_platforms:
        targeting["publisher_platforms"] = list(set(publisher_platforms))
        if facebook_positions:
            targeting["facebook_positions"] = list(set(facebook_positions))
        if instagram_positions:
            targeting["instagram_positions"] = list(set(instagram_positions))

    payload: dict = {
        "name": data.get("name", "AdSet"),
        "campaign_id": data["campaign_id"],
        "daily_budget": int(float(data.get("budget", 10)) * 100),
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "LEAD_GENERATION",
        "targeting": targeting,
        "status": "PAUSED",
    }

    if schedule := data.get("schedule", {}):
        if start := schedule.get("start_time"):
            payload["start_time"] = start
        if end := schedule.get("end_time"):
            payload["end_time"] = end

    result = client.post(f"{client.account_path}/adsets", payload)
    return {
        "id": result["id"],
        "campaign_id": data["campaign_id"],
        "meta_id": result["id"],
    }

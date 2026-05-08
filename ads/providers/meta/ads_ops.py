from __future__ import annotations

from .client import MetaAPIClient
from .creatives import create_creative


def create_ad(client: MetaAPIClient, data: dict, page_id: str) -> dict:
    image_hash: str | None = (
        data.get("image_hash")
        or (data.get("creative") or {}).get("image_hash")
    )

    creative = create_creative(client, data, page_id=page_id, image_hash=image_hash)

    payload: dict = {
        "name": data.get("name", "Ad"),
        "adset_id": data["adset_id"],
        "creative": {"creative_id": creative["id"]},
        "status": "PAUSED",
    }

    result = client.post(f"{client.account_path}/ads", payload)
    return {
        "id": result["id"],
        "campaign_id": data.get("campaign_id", ""),
        "adset_id": data["adset_id"],
        "meta_id": result["id"],
    }

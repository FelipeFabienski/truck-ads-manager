from __future__ import annotations

from .client import MetaAPIClient


def upload_image(client: MetaAPIClient, image_bytes: bytes, filename: str = "image.jpg") -> str:
    """Upload an image to the ad account and return its image_hash."""
    result = client.post_multipart(
        f"{client.account_path}/adimages",
        data={},
        files={"filename": (filename, image_bytes, "image/jpeg")},
    )
    # Response shape: {"images": {"<filename>": {"hash": "...", ...}}}
    for _name, info in result.get("images", {}).items():
        return info["hash"]
    raise ValueError("Image upload returned no hash")


def create_creative(
    client: MetaAPIClient,
    data: dict,
    page_id: str,
    image_hash: str | None = None,
) -> dict:
    link_data: dict = {
        "message": data.get("copy", ""),
        "name": data.get("headline", ""),
        "link": data.get("destination", ""),
        "call_to_action": {"type": "LEARN_MORE"},
    }

    if image_hash:
        link_data["image_hash"] = image_hash
    elif image_url := (data.get("creative") or {}).get("url"):
        link_data["picture"] = image_url

    payload: dict = {
        "name": f"Creative — {data.get('headline', '')}",
        "object_story_spec": {
            "page_id": page_id,
            "link_data": link_data,
        },
        "degrees_of_freedom_spec": {
            "creative_features_spec": {
                "standard_enhancements": {"enroll_status": "OPT_OUT"}
            }
        },
    }

    result = client.post(f"{client.account_path}/adcreatives", payload)
    return {"id": result["id"]}

from __future__ import annotations

import requests

from ..exceptions import AdsError, CampaignNotFound, CreationError, InvalidAccount
from ..provider import AdsProvider

_META_API_VERSION = "v19.0"
_META_BASE = f"https://graph.facebook.com/{_META_API_VERSION}"

# Mapeamento de status da Meta API → status interno
_META_STATUS_MAP: dict[str, str] = {
    "ACTIVE": "active",
    "PAUSED": "paused",
    "DELETED": "deleted",
    "ARCHIVED": "paused",
}

# Mapeamento de período → date_preset da Meta API
_PERIOD_MAP: dict[str, str] = {
    "today": "today",
    "last_7d": "last_7_days",
    "last_30d": "last_30_days",
}


class MetaAdsProvider(AdsProvider):
    """
    Provedor para a API real da Meta Ads (Facebook/Instagram).

    Requer:
        access_token   — User Access Token ou System User Token com permissão ads_management
        ad_account_id  — ID da conta de anúncios (sem prefixo "act_")

    Todos os métodos seguem a mesma assinatura do AdsProvider,
    garantindo substituição transparente pelo MockAdsProvider.
    """

    def __init__(self, access_token: str, ad_account_id: str) -> None:
        self._token = access_token
        self._account_id = ad_account_id
        self._account_url = f"{_META_BASE}/act_{ad_account_id}"

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _raise_for_meta_error(self, response: requests.Response) -> None:
        if response.ok:
            return
        error = response.json().get("error", {})
        code = error.get("code", 0)
        message = error.get("message", "Unknown Meta API error")
        # Códigos de autenticação/permissão da Meta
        if code in (190, 102, 200, 10):
            raise InvalidAccount(self._account_id)
        raise AdsError(message, f"META_{code}")

    def _post(self, url: str, payload: dict) -> dict:
        payload = {**payload, "access_token": self._token}
        response = requests.post(url, json=payload, headers=self._headers(), timeout=15)
        self._raise_for_meta_error(response)
        return response.json()

    def _get(self, path: str, params: dict | None = None) -> dict:
        params = {**(params or {}), "access_token": self._token}
        response = requests.get(f"{_META_BASE}/{path}", params=params, timeout=15)
        self._raise_for_meta_error(response)
        return response.json()

    def _patch(self, path: str, payload: dict) -> dict:
        payload = {**payload, "access_token": self._token}
        response = requests.post(f"{_META_BASE}/{path}", json=payload, headers=self._headers(), timeout=15)
        self._raise_for_meta_error(response)
        return response.json()

    # ── Campanhas ──────────────────────────────────────────────────────────────

    def create_campaign(self, data: dict) -> dict:
        if not data.get("name"):
            raise CreationError("campaign", "field 'name' is required")
        if not data.get("objective"):
            raise CreationError("campaign", "field 'objective' is required")

        payload = {
            "name": data["name"],
            "objective": data["objective"],
            "status": "PAUSED",
            "special_ad_categories": data.get("special_ad_categories", []),
        }
        if budget := data.get("budget"):
            payload["daily_budget"] = int(float(budget) * 100)  # Meta usa centavos

        result = self._post(f"{self._account_url}/campaigns", payload)
        return {
            "id": result["id"],
            "name": data["name"],
            "objective": data["objective"],
            "status": "draft",
            "budget": data.get("budget", 0),
            "created_at": None,
            "meta_id": result["id"],
        }

    def update_campaign(self, campaign_id: str, data: dict) -> dict:
        allowed_fields = {"name", "status", "daily_budget", "objective"}
        payload = {k: v for k, v in data.items() if k in allowed_fields}
        if "budget" in data and "daily_budget" not in payload:
            payload["daily_budget"] = int(float(data["budget"]) * 100)

        self._patch(campaign_id, payload)
        return {"id": campaign_id, **data}

    def get_campaign(self, campaign_id: str) -> dict:
        result = self._get(
            campaign_id,
            {"fields": "id,name,objective,status,daily_budget,created_time"},
        )
        return {
            "id": result["id"],
            "name": result.get("name"),
            "objective": result.get("objective"),
            "status": _META_STATUS_MAP.get(result.get("status", ""), "draft"),
            "budget": int(result.get("daily_budget", 0)) / 100,
            "created_at": result.get("created_time"),
            "meta_id": result["id"],
        }

    def list_campaigns(self, filters: dict | None = None) -> list[dict]:
        params: dict = {"fields": "id,name,objective,status,daily_budget,created_time"}
        if filters and "status" in filters:
            params["effective_status"] = [filters["status"].upper()]

        result = self._get(f"act_{self._account_id}/campaigns", params)
        return [
            {
                "id": c["id"],
                "name": c.get("name"),
                "objective": c.get("objective"),
                "status": _META_STATUS_MAP.get(c.get("status", ""), "draft"),
                "budget": int(c.get("daily_budget", 0)) / 100,
                "created_at": c.get("created_time"),
                "meta_id": c["id"],
            }
            for c in result.get("data", [])
        ]

    def delete_campaign(self, campaign_id: str) -> dict:
        self._patch(campaign_id, {"status": "DELETED"})
        return {"deleted": True, "campaign_id": campaign_id}

    # ── AdSets ─────────────────────────────────────────────────────────────────

    def create_adset(self, data: dict) -> dict:
        audience = data.get("audience", {})
        targeting: dict = {
            "geo_locations": {"countries": audience.get("locations", ["BR"])},
            "age_min": audience.get("age_min", 18),
            "age_max": audience.get("age_max", 65),
        }
        if interests := audience.get("interests"):
            targeting["flexible_spec"] = [{"interests": [{"name": i} for i in interests]}]
        if audience.get("gender") == "male":
            targeting["genders"] = [1]
        elif audience.get("gender") == "female":
            targeting["genders"] = [2]

        payload: dict = {
            "name": data.get("name", "AdSet"),
            "campaign_id": data["campaign_id"],
            "daily_budget": int(float(data.get("budget", 0)) * 100),
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

        result = self._post(f"{self._account_url}/adsets", payload)
        return {
            "id": result["id"],
            "campaign_id": data["campaign_id"],
            "meta_id": result["id"],
        }

    # ── Ads ────────────────────────────────────────────────────────────────────

    def create_ad(self, data: dict) -> dict:
        # 1. Criar o creative
        creative_payload: dict = {
            "name": f"Creative – {data.get('headline', '')}",
            "object_story_spec": {
                "page_id": data.get("page_id", ""),
                "link_data": {
                    "message": data.get("copy", ""),
                    "name": data.get("headline", ""),
                    "link": data.get("destination", ""),
                },
            },
        }
        creative = data.get("creative", {})
        if image_url := creative.get("url"):
            creative_payload["object_story_spec"]["link_data"]["picture"] = image_url

        creative_result = self._post(f"{self._account_url}/adcreatives", creative_payload)

        # 2. Criar o anúncio usando o creative
        ad_payload: dict = {
            "name": data.get("name", "Ad"),
            "adset_id": data["adset_id"],
            "creative": {"creative_id": creative_result["id"]},
            "status": "PAUSED",
        }
        result = self._post(f"{self._account_url}/ads", ad_payload)
        return {
            "id": result["id"],
            "campaign_id": data["campaign_id"],
            "adset_id": data["adset_id"],
            "meta_id": result["id"],
        }

    # ── Controle de estado ─────────────────────────────────────────────────────

    def pause_campaign(self, campaign_id: str) -> dict:
        return self.update_campaign(campaign_id, {"status": "PAUSED"})

    def activate_campaign(self, campaign_id: str) -> dict:
        return self.update_campaign(campaign_id, {"status": "ACTIVE"})

    # ── Métricas ───────────────────────────────────────────────────────────────

    def get_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        params = {
            "fields": "impressions,clicks,spend,actions",
            "date_preset": _PERIOD_MAP.get(period, "last_7_days"),
        }
        result = self._get(f"{campaign_id}/insights", params)
        data = result.get("data", [{}])[0] if result.get("data") else {}

        actions = {a["action_type"]: int(a["value"]) for a in data.get("actions", [])}
        leads = actions.get("lead", 0)
        spent = float(data.get("spend", 0))

        return {
            "campaign_id": campaign_id,
            "impressions": int(data.get("impressions", 0)),
            "clicks": int(data.get("clicks", 0)),
            "leads": leads,
            "spent": spent,
            "cpl": round(spent / leads, 2) if leads else 0.0,
            "period": period,
        }

    # ── Conta ──────────────────────────────────────────────────────────────────

    def validate_account(self, account_id: str) -> bool:
        result = self._get(f"act_{account_id}", {"fields": "id,name,account_status"})
        # account_status 1 = ACTIVE na Meta API
        if result.get("account_status") != 1:
            raise InvalidAccount(account_id)
        return True

    # ── Publicação orquestrada ─────────────────────────────────────────────────

    def publish_ad(self, data: dict) -> dict:
        campaign = self.create_campaign(data.get("campaign", {}))

        adset_data = {**data.get("adset", {}), "campaign_id": campaign["id"]}
        adset = self.create_adset(adset_data)

        ad_data = {
            **data.get("ad", {}),
            "campaign_id": campaign["id"],
            "adset_id": adset["id"],
        }
        ad = self.create_ad(ad_data)

        return {
            "success": True,
            "message": "Ad published to Meta Ads",
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
        }

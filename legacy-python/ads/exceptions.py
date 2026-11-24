class AdsError(Exception):
    def __init__(self, message: str, code: str = "ADS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": True, "code": self.code, "message": self.message}


class CampaignNotFound(AdsError):
    def __init__(self, campaign_id: str):
        super().__init__(f"Campaign '{campaign_id}' not found", "CAMPAIGN_NOT_FOUND")
        self.campaign_id = campaign_id


class AdSetNotFound(AdsError):
    def __init__(self, adset_id: str):
        super().__init__(f"AdSet '{adset_id}' not found", "ADSET_NOT_FOUND")
        self.adset_id = adset_id


class AdNotFound(AdsError):
    def __init__(self, ad_id: str):
        super().__init__(f"Ad '{ad_id}' not found", "AD_NOT_FOUND")
        self.ad_id = ad_id


class InvalidAccount(AdsError):
    def __init__(self, account_id: str):
        super().__init__(
            f"Account '{account_id}' is invalid or unauthorized", "INVALID_ACCOUNT"
        )
        self.account_id = account_id


class CreationError(AdsError):
    def __init__(self, entity: str, reason: str):
        super().__init__(f"Failed to create {entity}: {reason}", "CREATION_ERROR")
        self.entity = entity
        self.reason = reason


class InvalidTransition(AdsError):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(
            f"Invalid status transition: '{from_status}' → '{to_status}'",
            "INVALID_TRANSITION",
        )
        self.from_status = from_status
        self.to_status = to_status

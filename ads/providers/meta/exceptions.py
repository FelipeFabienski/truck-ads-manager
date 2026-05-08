from __future__ import annotations

from ads.exceptions import AdsError


class MetaAPIError(AdsError):
    def __init__(self, message: str, code: int = 0, subcode: int | None = None) -> None:
        super().__init__(message, f"META_{code}")
        self.meta_code = code
        self.meta_subcode = subcode


class MetaAuthError(MetaAPIError):
    """Token expired, revoked, or insufficient permissions (codes 190, 102)."""


class MetaRateLimitError(MetaAPIError):
    """API rate limit hit (codes 4, 17, 32, 613)."""


class MetaPermissionError(MetaAPIError):
    """Missing ads_management or ads_read permission (codes 10, 200)."""

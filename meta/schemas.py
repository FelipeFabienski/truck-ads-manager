from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetaCredentialCreate(BaseModel):
    name: str = Field(..., min_length=2)
    access_token: str = Field(..., min_length=10, description="Access Token Meta do cliente")
    ad_account_id: str = Field(..., min_length=1)
    page_id: str | None = None
    instagram_actor_id: str | None = None
    whatsapp_phone_number: str | None = None
    whatsapp_business_account_id: str | None = None

    @field_validator("ad_account_id")
    @classmethod
    def validate_ad_account_id(cls, v: str) -> str:
        stripped = v.strip()
        numeric = stripped
        while numeric.startswith("act_"):
            numeric = numeric[4:]
        if not numeric:
            raise ValueError(
                "ad_account_id deve conter um ID numérico válido (ex: 123456789 ou act_123456789)"
            )
        return stripped


class MetaCredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    access_token: str | None = Field(default=None, min_length=10)
    ad_account_id: str | None = None
    page_id: str | None = None
    instagram_actor_id: str | None = None
    whatsapp_phone_number: str | None = None
    whatsapp_business_account_id: str | None = None

    @field_validator("ad_account_id")
    @classmethod
    def validate_ad_account_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        numeric = stripped
        while numeric.startswith("act_"):
            numeric = numeric[4:]
        if not numeric:
            raise ValueError(
                "ad_account_id deve conter um ID numérico válido (ex: 123456789 ou act_123456789)"
            )
        return stripped


class MetaCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ad_account_id: str
    page_id: str | None
    instagram_actor_id: str | None
    whatsapp_phone_number: str | None
    whatsapp_business_account_id: str | None
    is_active: bool
    is_valid: bool
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MetaValidateResponse(BaseModel):
    valid: bool
    meta_user_id: str | None = None
    meta_user_name: str | None = None
    ad_account_name: str | None = None
    page_name: str | None = None
    message: str = ""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ads.providers.meta.credentials import (
    MetaTokenError,
    normalize_ad_account_id,
    validate_ad_account,
    validate_meta_token,
    validate_page,
)
from auth.crypto import decrypt, encrypt
from auth.dependencies import get_current_user
from db.database import get_db
from db.models.user import User

from .repository import MetaCredentialRepository
from .schemas import (
    MetaCredentialCreate,
    MetaCredentialResponse,
    MetaCredentialUpdate,
    MetaValidateResponse,
)

router = APIRouter(prefix="/meta/credentials", tags=["Meta Credentials"])

logger = logging.getLogger(__name__)


def _get_repo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MetaCredentialRepository:
    return MetaCredentialRepository(db, user_id=current_user.id)


def _run_validations(access_token: str, ad_account_id: str, page_id: str | None) -> None:
    """Validate token, ad account and (if provided) page against Meta API."""
    try:
        validate_meta_token(access_token)
    except MetaTokenError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    try:
        validate_ad_account(access_token, ad_account_id)
    except MetaTokenError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    if page_id:
        try:
            validate_page(access_token, page_id)
        except MetaTokenError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("", response_model=MetaCredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(
    body: MetaCredentialCreate,
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> MetaCredentialResponse:
    _run_validations(body.access_token, body.ad_account_id, body.page_id)
    record = repo.create(
        {
            "name": body.name,
            "access_token_enc": encrypt(body.access_token),
            "ad_account_id": normalize_ad_account_id(body.ad_account_id),
            "page_id": body.page_id,
            "instagram_actor_id": body.instagram_actor_id,
            "whatsapp_phone_number": body.whatsapp_phone_number,
            "whatsapp_business_account_id": body.whatsapp_business_account_id,
            "is_active": False,
        }
    )
    # Token passed validation above — mark as valid immediately
    record = repo.mark_validated(record.id)
    return MetaCredentialResponse.model_validate(record)


@router.get("", response_model=list[MetaCredentialResponse])
def list_credentials(
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> list[MetaCredentialResponse]:
    return [MetaCredentialResponse.model_validate(c) for c in repo.get_all()]


@router.get("/{credential_id}", response_model=MetaCredentialResponse)
def get_credential(
    credential_id: int,
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> MetaCredentialResponse:
    record = repo.get_by_id(credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada")
    return MetaCredentialResponse.model_validate(record)


@router.patch("/{credential_id}", response_model=MetaCredentialResponse)
def update_credential(
    credential_id: int,
    body: MetaCredentialUpdate,
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> MetaCredentialResponse:
    record = repo.get_by_id(credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada")

    update_data = body.model_dump(exclude_unset=True)

    if "access_token" in update_data:
        new_token = update_data.pop("access_token")
        new_ad_account = update_data.get("ad_account_id", record.ad_account_id)
        new_page_id = update_data.get("page_id", record.page_id)
        _run_validations(new_token, new_ad_account, new_page_id)
        update_data["access_token_enc"] = encrypt(new_token)

    if "ad_account_id" in update_data:
        try:
            update_data["ad_account_id"] = normalize_ad_account_id(update_data["ad_account_id"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = repo.update(record, update_data)
    return MetaCredentialResponse.model_validate(record)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: int,
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> None:
    record = repo.get_by_id(credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada")
    repo.delete(record)


@router.post("/{credential_id}/set-active", response_model=MetaCredentialResponse)
def set_active(
    credential_id: int,
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> MetaCredentialResponse:
    record = repo.get_by_id(credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada")
    record = repo.set_active(credential_id)
    return MetaCredentialResponse.model_validate(record)


@router.post("/{credential_id}/validate", response_model=MetaValidateResponse)
def validate_credential(
    credential_id: int,
    repo: MetaCredentialRepository = Depends(_get_repo),
) -> MetaValidateResponse:
    record = repo.get_by_id(credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada")

    try:
        access_token = decrypt(record.access_token_enc)
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao descriptografar token.")

    collected: dict = {}

    try:
        me = validate_meta_token(access_token)
        collected["meta_user_id"] = me.get("id")
        collected["meta_user_name"] = me.get("name")
    except MetaTokenError as exc:
        repo.mark_invalid(credential_id)
        return MetaValidateResponse(valid=False, message=str(exc))

    try:
        account = validate_ad_account(access_token, record.ad_account_id)
        collected["ad_account_name"] = account.get("name")
    except MetaTokenError as exc:
        repo.mark_invalid(credential_id)
        return MetaValidateResponse(valid=False, message=str(exc), **collected)

    if record.page_id:
        try:
            page = validate_page(access_token, record.page_id)
            collected["page_name"] = page.get("name")
        except MetaTokenError as exc:
            repo.mark_invalid(credential_id)
            return MetaValidateResponse(valid=False, message=str(exc), **collected)

    repo.mark_validated(credential_id)
    return MetaValidateResponse(valid=True, message="Credencial válida.", **collected)

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ads.exceptions import (
    AdsError,
    CampaignNotFound,
    CreationError,
    InvalidAccount,
    InvalidTransition,
)


def register_error_handlers(app: FastAPI) -> None:
    """Registra um handler HTTP por tipo de AdsError."""

    @app.exception_handler(CampaignNotFound)
    async def _campaign_not_found(request: Request, exc: CampaignNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content=exc.to_dict())

    @app.exception_handler(InvalidTransition)
    async def _invalid_transition(request: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content=exc.to_dict())

    @app.exception_handler(InvalidAccount)
    async def _invalid_account(request: Request, exc: InvalidAccount) -> JSONResponse:
        return JSONResponse(status_code=403, content=exc.to_dict())

    @app.exception_handler(CreationError)
    async def _creation_error(request: Request, exc: CreationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=exc.to_dict())

    # Handler base: captura qualquer AdsError não tratado acima
    @app.exception_handler(AdsError)
    async def _ads_error(request: Request, exc: AdsError) -> JSONResponse:
        return JSONResponse(status_code=500, content=exc.to_dict())

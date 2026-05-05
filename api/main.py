from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .error_handlers import register_error_handlers
from .routers import truck_router
from .schemas import HealthResponse

_ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Força a inicialização do singleton na startup — falha rápido se env vars faltarem
    from .dependencies import _build_service
    _build_service()
    yield


def create_app(title: str = "Truck Ads Manager API") -> FastAPI:
    app = FastAPI(
        title=title,
        version="1.0.0",
        description="API de gestão de campanhas de anúncios de caminhões (Meta Ads)",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Em produção, substitua "*" pelos domínios reais via CORS_ORIGINS no env.
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Error handlers ────────────────────────────────────────────────────────
    register_error_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(truck_router, prefix="/ads/truck", tags=["Truck Ads"])

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["Sistema"])
    def health() -> dict:
        return {"status": "ok", "provider": os.getenv("ADS_PROVIDER", "mock")}

    # ── Frontend ──────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(_ROOT / "index.html")

    return app


# Instância usada pelo servidor ASGI (uvicorn api.main:app)
app = create_app()

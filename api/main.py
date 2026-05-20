from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from auth.routes import router as auth_router

from .error_handlers import register_error_handlers
from .routers import truck_router
from .schemas import HealthResponse

_ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    import db.models  # noqa: F401 — register all models with Base.metadata
    from alembic import command as alembic_command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from db.database import Base, engine

    logger = logging.getLogger(__name__)

    if engine.dialect.name == "postgresql":
        alembic_cfg = Config(str(_ROOT / "alembic.ini"))

        # 1. Run Alembic migrations (handles schema changes on existing tables).
        try:
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("alembic upgrade head: OK")
        except Exception as exc:
            logger.warning("alembic upgrade head failed: %s", exc)

        # 2. Fallback: create any tables still missing from current model definitions.
        try:
            Base.metadata.create_all(engine)
            logger.info("create_all: tables ensured")
        except Exception as exc:
            logger.warning("create_all failed: %s", exc)

        # 3. If alembic_version is empty, stamp to head so future runs are no-ops.
        try:
            with engine.connect() as conn:
                if MigrationContext.configure(conn).get_current_revision() is None:
                    alembic_command.stamp(alembic_cfg, "head")
                    logger.info("alembic stamped to head")
        except Exception as exc:
            logger.warning("alembic stamp skipped: %s", exc)

    yield


def create_app(title: str = "Truck Ads Manager API") -> FastAPI:
    app = FastAPI(
        title=title,
        version="2.0.0",
        description="SaaS para vendedores e lojas de caminhões criarem, publicarem e gerenciarem campanhas no Meta Ads usando credenciais Meta próprias de cada cliente.",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
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
    app.include_router(auth_router)
    app.include_router(truck_router, prefix="/ads/truck", tags=["Truck Ads"])

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["Sistema"])
    def health() -> dict:
        return {"status": "ok", "provider": os.getenv("ADS_PROVIDER", "mock")}

    @app.get("/version", include_in_schema=False)
    def version() -> dict:
        return {"etapa": 3, "commit": "2f5e848"}



    # ── Frontend ──────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(_ROOT / "index.html")

    return app


app = create_app()

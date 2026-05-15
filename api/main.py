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
    # Ensure email-verification and password-reset columns exist.
    # PostgreSQL-only syntax (IF NOT EXISTS); skipped silently on SQLite (tests).
    import logging
    from sqlalchemy import text
    from db.database import engine
    if engine.dialect.name == "postgresql":
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR, "
                    "ADD COLUMN IF NOT EXISTS email_verification_expires_at TIMESTAMPTZ, "
                    "ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR, "
                    "ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMPTZ"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_users_email_verification_token "
                    "ON users (email_verification_token)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_users_password_reset_token "
                    "ON users (password_reset_token)"
                ))
                conn.commit()
        except Exception as exc:
            logging.getLogger(__name__).warning("Lifespan migration skipped: %s", exc)
    yield


def create_app(title: str = "Truck Ads Manager API") -> FastAPI:
    app = FastAPI(
        title=title,
        version="2.0.0",
        description="API de gestão de campanhas de anúncios de caminhões (Meta Ads + PostgreSQL)",
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
        return {"etapa": 3, "commit": "0838ec6"}

    # ── Frontend ──────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(_ROOT / "index.html")

    return app


app = create_app()

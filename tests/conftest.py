from __future__ import annotations

import warnings
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import db.models  # noqa: F401 — register all models with Base.metadata
from api.main import create_app
from db.database import Base, get_db

_SQLITE_URL = "sqlite:///:memory:"


def pytest_configure(config):  # type: ignore[no-untyped-def]
    # Field named 'copy' is an intentional advertising term; suppress the Pydantic shadow warning
    warnings.filterwarnings("ignore", message="Field name.*shadows an attribute in parent")


@pytest.fixture(scope="function")
def _engine():  # type: ignore[no-untyped-def]
    engine = create_engine(
        _SQLITE_URL,
        connect_args={"check_same_thread": False},
        # StaticPool reuses a single connection so all sessions see the same DB
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(_engine) -> Generator[Session, None, None]:  # type: ignore[no-untyped-def]
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def auth_client(test_db: Session) -> TestClient:
    """TestClient with real SQLite DB, no get_current_user override."""

    def _override_db() -> Generator[Session, None, None]:
        yield test_db

    app = create_app()
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)

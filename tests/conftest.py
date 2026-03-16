import socket
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session as SyncSession
from sqlalchemy.pool import NullPool

from alembic import command
from app.config import settings
from app.dependencies import get_session
from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_test_engine = create_async_engine(
    settings.test_database_url,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,
)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail immediately with a clear message if the test database is unreachable."""
    parsed = urlparse(settings.test_database_url.replace("postgresql+asyncpg", "postgresql"))
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=3.0):
            pass
    except OSError as exc:
        pytest.exit(
            f"\nTest database unreachable — start it first:\n"
            f"  docker compose up -d db_test\n\n"
            f"Expected at: {settings.test_database_url}\n"
            f"Error: {exc}",
            returncode=1,
        )

    try:
        alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
        alembic_cfg.attributes["database_url"] = settings.test_database_url
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:  # pragma: no cover - hard-fail startup path
        pytest.exit(
            f"\nFailed to apply migrations to test database.\n"
            f"Expected at: {settings.test_database_url}\n"
            f"Error: {type(exc).__name__}: {exc}",
            returncode=1,
        )


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _test_engine.connect() as conn:
        outer_tx = await conn.begin()
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            await conn.begin_nested()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sync_sess: SyncSession, tx: Any) -> None:
                """Recreate the savepoint after each commit so rollback isolation
                holds for any test that calls session.commit() internally."""
                if tx.nested and tx._parent is not None and not tx._parent.nested:
                    sync_sess.begin_nested()

            yield session
        await outer_tx.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

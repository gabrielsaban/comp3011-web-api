import asyncio
from collections.abc import AsyncGenerator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.dependencies import get_session
from app.main import app

_test_engine = create_async_engine(settings.test_database_url, echo=False, pool_pre_ping=True)
_TestSessionLocal = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail immediately with a clear message if the test database is unreachable."""

    async def _check() -> None:
        dsn = settings.test_database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=3.0)
        await conn.close()

    try:
        asyncio.run(_check())
    except Exception as exc:
        pytest.exit(
            f"\nTest database unreachable — start it first:\n"
            f"  docker compose up -d db_test\n\n"
            f"Expected at: {settings.test_database_url}\n"
            f"Error: {type(exc).__name__}: {exc}",
            returncode=1,
        )


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _test_engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            await conn.begin_nested()
            yield session
        await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

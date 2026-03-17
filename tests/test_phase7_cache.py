from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from tests.fixtures.seed import seed_profile


@pytest.mark.asyncio
async def test_build_startup_caches_from_analytics_fixture(db_session: AsyncSession) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    await cache.build_startup_caches(db_session)

    assert cache.HEATMAP[2][8] == 1
    assert cache.HEATMAP[5][17] == 2
    assert cache.HEATMAP[7][2] == 1
    assert cache.HEATMAP[1][8] == 1

    assert cache.SPEED_FATAL_RATES[20] == 0.0
    assert cache.SPEED_FATAL_RATES[30] == 0.0
    assert cache.SPEED_FATAL_RATES[40] == 50.0
    assert cache.SPEED_FATAL_RATES[60] == 100.0

    assert pytest.approx(7.88, abs=0.01) == cache.P99_DENSITY

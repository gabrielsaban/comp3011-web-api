from __future__ import annotations

from math import ceil, floor

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accident import Accident

# Route-risk startup caches (loaded from DB state, not request-time writes).
HEATMAP: dict[int, dict[int, int]] = {}
SPEED_FATAL_RATES: dict[int, float] = {}
P99_DENSITY: float = 0.0

GRID_CELL_DEGREES = 0.005
GRID_CELL_KM = 0.5


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * percentile
    lo = floor(rank)
    hi = ceil(rank)
    if lo == hi:
        return ordered[lo]

    weight = rank - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def _empty_heatmap() -> dict[int, dict[int, int]]:
    return {day: {hour: 0 for hour in range(24)} for day in range(1, 8)}


def reset_startup_caches() -> None:
    HEATMAP.clear()
    SPEED_FATAL_RATES.clear()
    global P99_DENSITY
    P99_DENSITY = 0.0


async def build_startup_caches(session: AsyncSession) -> None:
    reset_startup_caches()

    heatmap = _empty_heatmap()
    heatmap_rows = await session.execute(
        select(
            Accident.day_of_week.label("day_of_week"),
            func.extract("hour", Accident.time).label("hour_of_day"),
            func.count().label("total"),
        )
        .where(Accident.day_of_week.is_not(None), Accident.time.is_not(None))
        .group_by(Accident.day_of_week, func.extract("hour", Accident.time))
    )
    for row in heatmap_rows:
        day = int(row.day_of_week)
        hour = int(row.hour_of_day)
        if day in heatmap and 0 <= hour <= 23:
            heatmap[day][hour] = int(row.total)

    HEATMAP.update(heatmap)

    speed_rows = await session.execute(
        select(
            Accident.speed_limit.label("speed_limit"),
            func.sum(case((Accident.severity_id == 1, 1), else_=0)).label("fatal"),
            func.count().label("total"),
        )
        .where(Accident.speed_limit.is_not(None))
        .group_by(Accident.speed_limit)
    )
    for row in speed_rows:
        speed_limit = int(row.speed_limit)
        total = int(row.total or 0)
        fatal = int(row.fatal or 0)
        rate = (fatal * 100.0 / total) if total > 0 else 0.0
        SPEED_FATAL_RATES[speed_limit] = rate

    lat_bin = func.floor(Accident.latitude / GRID_CELL_DEGREES)
    lng_bin = func.floor(Accident.longitude / GRID_CELL_DEGREES)
    density_rows = await session.execute(
        select(
            lat_bin.label("lat_bin"),
            lng_bin.label("lng_bin"),
            func.count().label("total"),
        )
        .where(Accident.latitude.is_not(None), Accident.longitude.is_not(None))
        .group_by(lat_bin, lng_bin)
    )
    densities = [int(row.total) / (GRID_CELL_KM * GRID_CELL_KM) for row in density_rows]

    global P99_DENSITY
    P99_DENSITY = _percentile(densities, 0.99)

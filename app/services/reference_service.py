from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lookups import (
    JunctionDetail,
    LightCondition,
    RoadSurface,
    RoadType,
    Severity,
    VehicleType,
    WeatherCondition,
)
from app.schemas.accident import IdLabel

ALL_LOOKUPS: dict[str, type] = {
    "severities": Severity,
    "weather_conditions": WeatherCondition,
    "light_conditions": LightCondition,
    "road_surfaces": RoadSurface,
    "road_types": RoadType,
    "junction_details": JunctionDetail,
    "vehicle_types": VehicleType,
}

TYPE_TO_KEY: dict[str, str] = {
    "weather": "weather_conditions",
    "light": "light_conditions",
    "road_surface": "road_surfaces",
    "road_type": "road_types",
    "junction": "junction_details",
    "vehicle_type": "vehicle_types",
}


def _query_for_key(key: str) -> Any:
    if key == "severities":
        return select(Severity).order_by(Severity.id.asc())
    if key == "weather_conditions":
        return select(WeatherCondition).order_by(WeatherCondition.id.asc())
    if key == "light_conditions":
        return select(LightCondition).order_by(LightCondition.id.asc())
    if key == "road_surfaces":
        return select(RoadSurface).order_by(RoadSurface.id.asc())
    if key == "road_types":
        return select(RoadType).order_by(RoadType.id.asc())
    if key == "junction_details":
        return select(JunctionDetail).order_by(JunctionDetail.id.asc())
    if key == "vehicle_types":
        return select(VehicleType).order_by(VehicleType.id.asc())
    raise ValueError(f"Unknown lookup key: {key}")


async def list_reference_conditions(
    session: AsyncSession,
    condition_type: str | None,
) -> dict[str, list[IdLabel]]:
    if condition_type is not None and condition_type not in TYPE_TO_KEY:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid type parameter. Expected one of: "
                "weather, light, road_surface, road_type, junction, vehicle_type."
            ),
        )

    keys = [TYPE_TO_KEY[condition_type]] if condition_type else list(ALL_LOOKUPS.keys())
    result: dict[str, list[IdLabel]] = {}
    for key in keys:
        rows = (await session.scalars(_query_for_key(key))).all()
        result[key] = [IdLabel(id=row.id, label=row.label) for row in rows]
    return result

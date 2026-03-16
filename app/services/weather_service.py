from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accident import Accident
from app.models.lookups import LocalAuthority
from app.models.weather import WeatherObservation, WeatherStation
from app.schemas.weather import (
    WeatherObservationSummary,
    WeatherStationCollectionMeta,
    WeatherStationDetail,
    WeatherStationListItem,
)


def _linked_accident_counts_subquery(region_id: int | None) -> Any:
    query = (
        select(
            WeatherObservation.station_id.label("station_id"),
            func.count(Accident.id).label("linked_accident_count"),
        )
        .join(Accident, Accident.weather_observation_id == WeatherObservation.id)
        .group_by(WeatherObservation.station_id)
    )
    if region_id is not None:
        query = query.join(LocalAuthority, LocalAuthority.id == Accident.local_authority_id).where(
            LocalAuthority.region_id == region_id
        )
    return query.subquery()


async def list_weather_stations(
    session: AsyncSession,
    page: int,
    per_page: int,
    region_id: int | None,
    active_on: date | None,
) -> tuple[list[WeatherStationListItem], WeatherStationCollectionMeta]:
    linked_counts = _linked_accident_counts_subquery(region_id)
    query = (
        select(WeatherStation, linked_counts.c.linked_accident_count)
        .join(linked_counts, linked_counts.c.station_id == WeatherStation.id)
        .order_by(WeatherStation.name.asc())
    )
    if active_on is not None:
        query = query.where(
            func.coalesce(WeatherStation.active_from <= active_on, True),
            func.coalesce(WeatherStation.active_to >= active_on, True),
        )

    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    rows = (
        await session.execute(query.offset((page - 1) * per_page).limit(per_page))
    ).all()

    data = [
        WeatherStationListItem(
            id=station.id,
            name=station.name,
            latitude=station.latitude,
            longitude=station.longitude,
            elevation_m=station.elevation_m,
            active_from=station.active_from,
            active_to=station.active_to,
            linked_accident_count=int(linked_accident_count),
        )
        for station, linked_accident_count in rows
    ]
    meta = WeatherStationCollectionMeta(page=page, per_page=per_page, total=total)
    return data, meta


async def get_weather_station(session: AsyncSession, station_id: int) -> WeatherStationDetail:
    linked_counts = _linked_accident_counts_subquery(region_id=None)
    station_row = (
        await session.execute(
            select(WeatherStation, linked_counts.c.linked_accident_count)
            .join(linked_counts, linked_counts.c.station_id == WeatherStation.id)
            .where(WeatherStation.id == station_id)
        )
    ).first()
    if station_row is None:
        raise HTTPException(status_code=404, detail="Weather station not found.")

    station, linked_accident_count = station_row
    linked_observations = (
        select(WeatherObservation.id)
        .join(Accident, Accident.weather_observation_id == WeatherObservation.id)
        .where(WeatherObservation.station_id == station_id)
        .distinct()
    ).subquery()

    summary_row = (
        await session.execute(
            select(
                func.avg(WeatherObservation.temperature_c).label("mean_temperature_c"),
                func.avg(WeatherObservation.precipitation_mm).label("mean_precipitation_mm"),
                func.avg(WeatherObservation.wind_speed_ms).label("mean_wind_speed_ms"),
                func.avg(WeatherObservation.visibility_m).label("mean_visibility_m"),
                func.sum(
                    case((WeatherObservation.precipitation_mm > 0, 1), else_=0)
                ).label("observations_with_precipitation"),
            ).where(WeatherObservation.id.in_(select(linked_observations.c.id)))
        )
    ).first()

    mean_temperature_c = (
        float(summary_row.mean_temperature_c)
        if summary_row is not None and summary_row.mean_temperature_c is not None
        else None
    )
    mean_precipitation_mm = (
        float(summary_row.mean_precipitation_mm)
        if summary_row is not None and summary_row.mean_precipitation_mm is not None
        else None
    )
    mean_wind_speed_ms = (
        float(summary_row.mean_wind_speed_ms)
        if summary_row is not None and summary_row.mean_wind_speed_ms is not None
        else None
    )
    mean_visibility_m = (
        float(summary_row.mean_visibility_m)
        if summary_row is not None and summary_row.mean_visibility_m is not None
        else None
    )
    observations_with_precipitation = (
        int(summary_row.observations_with_precipitation or 0) if summary_row is not None else 0
    )
    summary = WeatherObservationSummary(
        mean_temperature_c=mean_temperature_c,
        mean_precipitation_mm=mean_precipitation_mm,
        mean_wind_speed_ms=mean_wind_speed_ms,
        mean_visibility_m=mean_visibility_m,
        observations_with_precipitation=observations_with_precipitation,
    )

    return WeatherStationDetail(
        id=station.id,
        name=station.name,
        latitude=station.latitude,
        longitude=station.longitude,
        elevation_m=station.elevation_m,
        active_from=station.active_from,
        active_to=station.active_to,
        linked_accident_count=int(linked_accident_count),
        observation_summary=summary,
    )

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas.weather import WeatherStationCollectionResponse, WeatherStationItemResponse
from app.services.weather_service import get_weather_station, list_weather_stations

router = APIRouter(prefix="/api/v1/weather-stations", tags=["Weather"])


@router.get("", response_model=WeatherStationCollectionResponse)
async def get_weather_stations(
    db: DbSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    region_id: int | None = None,
    active_on: date | None = None,
) -> WeatherStationCollectionResponse:
    data, meta = await list_weather_stations(db, page, per_page, region_id, active_on)
    return WeatherStationCollectionResponse(data=data, meta=meta)


@router.get("/{station_id}", response_model=WeatherStationItemResponse)
async def get_weather_station_by_id(station_id: int, db: DbSession) -> WeatherStationItemResponse:
    return WeatherStationItemResponse(data=await get_weather_station(db, station_id))

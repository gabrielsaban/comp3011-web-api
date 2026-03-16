from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.accident import MetaPagination


class WeatherStationListItem(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    elevation_m: int | None
    active_from: date | None
    active_to: date | None
    linked_accident_count: int


class WeatherStationCollectionResponse(BaseModel):
    data: list[WeatherStationListItem]
    meta: MetaPagination


class WeatherObservationSummary(BaseModel):
    mean_temperature_c: float | None
    mean_precipitation_mm: float | None
    mean_wind_speed_ms: float | None
    mean_visibility_m: float | None
    observations_with_precipitation: int


class WeatherStationDetail(WeatherStationListItem):
    observation_summary: WeatherObservationSummary


class WeatherStationItemResponse(BaseModel):
    data: WeatherStationDetail

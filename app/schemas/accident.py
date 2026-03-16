from __future__ import annotations

from datetime import date as DateValue
from datetime import time as TimeValue
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetaPagination(BaseModel):
    page: int
    per_page: int
    total: int


class IdLabel(BaseModel):
    id: int
    label: str


class NamedRef(BaseModel):
    id: int
    name: str


class WeatherObservationResponse(BaseModel):
    station_id: int
    station_name: str
    station_distance_km: float
    temperature_c: float | None
    precipitation_mm: float | None
    wind_speed_ms: float | None
    visibility_m: int | None


class VehicleResponse(BaseModel):
    vehicle_ref: int
    vehicle_type: IdLabel | None
    age_of_driver: int | None
    sex_of_driver: str | None
    engine_capacity_cc: int | None
    propulsion_code: str | None
    age_of_vehicle: int | None
    journey_purpose: str | None


class CasualtyResponse(BaseModel):
    casualty_ref: int
    vehicle_ref: int | None
    severity: IdLabel
    casualty_class: str | None
    casualty_type: str | None
    sex: str | None
    age: int | None
    age_band: str | None


class AccidentListItem(BaseModel):
    id: str
    date: DateValue
    time: TimeValue | None
    day_of_week: int | None
    latitude: float | None
    longitude: float | None
    severity: IdLabel
    speed_limit: int | None
    urban_or_rural: str | None
    number_of_vehicles: int
    number_of_casualties: int
    local_authority: NamedRef | None
    region: NamedRef | None


class AccidentDetail(AccidentListItem):
    road_type: IdLabel | None
    junction_detail: IdLabel | None
    light_condition: IdLabel | None
    weather_condition: IdLabel | None
    road_surface: IdLabel | None
    police_attended: bool | None
    cluster_id: int | None
    weather_observation: WeatherObservationResponse | None
    vehicles: list[VehicleResponse]
    casualties: list[CasualtyResponse]


class AccidentCollectionResponse(BaseModel):
    data: list[AccidentListItem]
    meta: MetaPagination


class AccidentListResponse(BaseModel):
    data: AccidentListItem


class AccidentDetailResponse(BaseModel):
    data: AccidentDetail


class AccidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: DateValue
    time: TimeValue | None = None
    day_of_week: int = Field(ge=1, le=7)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    severity_id: int
    road_type_id: int | None = None
    junction_detail_id: int | None = None
    light_condition_id: int | None = None
    weather_condition_id: int | None = None
    road_surface_id: int | None = None
    speed_limit: int | None = None
    local_authority_id: int | None = None
    urban_or_rural: Literal["Urban", "Rural", "Unallocated"] | None = None
    police_attended: bool | None = None


class AccidentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: DateValue | None = None
    time: TimeValue | None = None
    day_of_week: int | None = Field(default=None, ge=1, le=7)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    severity_id: int | None = None
    road_type_id: int | None = None
    junction_detail_id: int | None = None
    light_condition_id: int | None = None
    weather_condition_id: int | None = None
    road_surface_id: int | None = None
    speed_limit: int | None = None
    local_authority_id: int | None = None
    urban_or_rural: Literal["Urban", "Rural", "Unallocated"] | None = None
    police_attended: bool | None = None
    number_of_vehicles: int | None = None
    number_of_casualties: int | None = None

    @field_validator("number_of_vehicles", "number_of_casualties")
    @classmethod
    def reject_count_fields(cls, value: int | None) -> int | None:
        if value is not None:
            raise ValueError("This field is managed by the API and cannot be patched.")
        return value

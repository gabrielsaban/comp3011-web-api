from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import asin, cos, radians, sin, sqrt
from secrets import randbelow

from fastapi import HTTPException
from sqlalchemy import asc, delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import Select

from app.models.accident import Accident, Casualty, Vehicle
from app.models.lookups import LocalAuthority
from app.models.weather import WeatherObservation
from app.schemas.accident import (
    AccidentCreate,
    AccidentDetail,
    AccidentListItem,
    AccidentPatch,
    CasualtyResponse,
    IdLabel,
    NamedRef,
    VehicleResponse,
    WeatherObservationResponse,
)


@dataclass(slots=True)
class AccidentListFilters:
    page: int = 1
    per_page: int = 25
    sort: str = "date"
    order: str = "desc"
    date_from: date | None = None
    date_to: date | None = None
    severity: int | None = None
    region_id: int | None = None
    local_authority_id: int | None = None
    road_type_id: int | None = None
    weather_condition_id: int | None = None
    light_condition_id: int | None = None
    speed_limit: int | None = None
    urban_or_rural: str | None = None
    cluster_id: int | None = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return earth_radius_km * 2 * asin(sqrt(a))


def _new_accident_id() -> str:
    # Random suffix collision probability is acceptable for coursework/demo writes.
    # API-created rows are ephemeral between full-import refresh cycles by design.
    prefix = datetime.now(UTC).strftime("%Y")
    return f"{prefix}{randbelow(10**9):09d}"


def _id_label(id_value: int | None, label: str | None) -> IdLabel | None:
    if id_value is None or label is None:
        return None
    return IdLabel(id=id_value, label=label)


def _named_ref(id_value: int | None, name: str | None) -> NamedRef | None:
    if id_value is None or name is None:
        return None
    return NamedRef(id=id_value, name=name)


def _to_list_item(accident: Accident) -> AccidentListItem:
    return AccidentListItem(
        id=accident.id,
        date=accident.date,
        time=accident.time,
        day_of_week=accident.day_of_week,
        latitude=accident.latitude,
        longitude=accident.longitude,
        severity=IdLabel(id=accident.severity_id, label=accident.severity.label),
        speed_limit=accident.speed_limit,
        urban_or_rural=accident.urban_or_rural,
        number_of_vehicles=accident.number_of_vehicles,
        number_of_casualties=accident.number_of_casualties,
        local_authority=_named_ref(
            accident.local_authority_id,
            accident.local_authority.name if accident.local_authority else None,
        ),
        region=_named_ref(
            accident.local_authority.region.id
            if accident.local_authority and accident.local_authority.region
            else None,
            accident.local_authority.region.name
            if accident.local_authority and accident.local_authority.region
            else None,
        ),
    )


def _to_vehicle_response(vehicle: Vehicle) -> VehicleResponse:
    return VehicleResponse(
        vehicle_ref=vehicle.vehicle_ref,
        vehicle_type=_id_label(
            vehicle.vehicle_type_id,
            vehicle.vehicle_type.label if vehicle.vehicle_type else None,
        ),
        age_of_driver=vehicle.age_of_driver,
        sex_of_driver=vehicle.sex_of_driver,
        engine_capacity_cc=vehicle.engine_capacity_cc,
        propulsion_code=vehicle.propulsion_code,
        age_of_vehicle=vehicle.age_of_vehicle,
        journey_purpose=vehicle.journey_purpose,
    )


def _to_casualty_response(casualty: Casualty) -> CasualtyResponse:
    return CasualtyResponse(
        casualty_ref=casualty.casualty_ref,
        vehicle_ref=casualty.vehicle_ref,
        severity=IdLabel(id=casualty.severity_id, label=casualty.severity.label),
        casualty_class=casualty.casualty_class,
        casualty_type=casualty.casualty_type,
        sex=casualty.sex,
        age=casualty.age,
        age_band=casualty.age_band,
    )


def _weather_response(accident: Accident) -> WeatherObservationResponse | None:
    obs = accident.weather_observation
    if obs is None or obs.station is None:
        return None
    if accident.latitude is None or accident.longitude is None:
        return None

    return WeatherObservationResponse(
        station_id=obs.station_id,
        station_name=obs.station.name,
        station_distance_km=round(
            _haversine_km(
                accident.latitude,
                accident.longitude,
                obs.station.latitude,
                obs.station.longitude,
            ),
            3,
        ),
        temperature_c=obs.temperature_c,
        precipitation_mm=obs.precipitation_mm,
        wind_speed_ms=obs.wind_speed_ms,
        visibility_m=obs.visibility_m,
    )


def _apply_filters(query: Select, filters: AccidentListFilters) -> Select:
    if filters.date_from is not None:
        query = query.where(Accident.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Accident.date <= filters.date_to)
    if filters.severity is not None:
        query = query.where(Accident.severity_id == filters.severity)
    if filters.region_id is not None:
        query = query.where(
            Accident.local_authority.has(LocalAuthority.region_id == filters.region_id)
        )
    if filters.local_authority_id is not None:
        query = query.where(Accident.local_authority_id == filters.local_authority_id)
    if filters.road_type_id is not None:
        query = query.where(Accident.road_type_id == filters.road_type_id)
    if filters.weather_condition_id is not None:
        query = query.where(Accident.weather_condition_id == filters.weather_condition_id)
    if filters.light_condition_id is not None:
        query = query.where(Accident.light_condition_id == filters.light_condition_id)
    if filters.speed_limit is not None:
        query = query.where(Accident.speed_limit == filters.speed_limit)
    if filters.urban_or_rural is not None:
        query = query.where(Accident.urban_or_rural == filters.urban_or_rural)
    if filters.cluster_id is not None:
        query = query.where(Accident.cluster_id == filters.cluster_id)
    return query


async def list_accidents(
    session: AsyncSession,
    filters: AccidentListFilters,
) -> tuple[list[AccidentListItem], int]:
    total_query = _apply_filters(select(func.count()).select_from(Accident), filters)
    total = int((await session.scalar(total_query)) or 0)

    query = select(Accident).options(
        joinedload(Accident.severity),
        joinedload(Accident.local_authority).joinedload(LocalAuthority.region),
    )
    query = _apply_filters(query, filters)

    sort_map = {"date": Accident.date, "severity": Accident.severity_id}
    sort_column = sort_map.get(filters.sort, Accident.date)
    order_by = desc(sort_column) if filters.order == "desc" else asc(sort_column)

    query = (
        query.order_by(order_by)
        .offset((filters.page - 1) * filters.per_page)
        .limit(filters.per_page)
    )

    accidents = (await session.scalars(query)).unique().all()
    return [_to_list_item(accident) for accident in accidents], total


async def get_accident_detail(session: AsyncSession, accident_id: str) -> AccidentDetail:
    # 1) Fetch accident row and dimension relationships.
    accident_query = (
        select(Accident)
        .options(
            joinedload(Accident.severity),
            joinedload(Accident.road_type),
            joinedload(Accident.junction_detail),
            joinedload(Accident.light_condition),
            joinedload(Accident.weather_condition),
            joinedload(Accident.road_surface),
            joinedload(Accident.local_authority).joinedload(LocalAuthority.region),
            joinedload(Accident.weather_observation).joinedload(WeatherObservation.station),
        )
        .where(Accident.id == accident_id)
    )
    accident = (await session.scalars(accident_query)).first()
    if accident is None:
        raise HTTPException(status_code=404, detail="Accident not found.")

    # 2) Fetch vehicles for this accident.
    vehicle_query = (
        select(Vehicle)
        .options(joinedload(Vehicle.vehicle_type))
        .where(Vehicle.accident_id == accident_id)
        .order_by(Vehicle.vehicle_ref.asc())
    )
    vehicles = (await session.scalars(vehicle_query)).all()

    # 3) Fetch casualties for this accident.
    casualty_query = (
        select(Casualty)
        .options(joinedload(Casualty.severity))
        .where(Casualty.accident_id == accident_id)
        .order_by(Casualty.casualty_ref.asc())
    )
    casualties = (await session.scalars(casualty_query)).all()

    list_item = _to_list_item(accident)
    return AccidentDetail(
        **list_item.model_dump(),
        road_type=_id_label(
            accident.road_type_id,
            accident.road_type.label if accident.road_type else None,
        ),
        junction_detail=_id_label(
            accident.junction_detail_id,
            accident.junction_detail.label if accident.junction_detail else None,
        ),
        light_condition=_id_label(
            accident.light_condition_id,
            accident.light_condition.label if accident.light_condition else None,
        ),
        weather_condition=_id_label(
            accident.weather_condition_id,
            accident.weather_condition.label if accident.weather_condition else None,
        ),
        road_surface=_id_label(
            accident.road_surface_id,
            accident.road_surface.label if accident.road_surface else None,
        ),
        police_attended=accident.police_attended,
        cluster_id=accident.cluster_id,
        weather_observation=_weather_response(accident),
        vehicles=[_to_vehicle_response(vehicle) for vehicle in vehicles],
        casualties=[_to_casualty_response(casualty) for casualty in casualties],
    )


async def create_accident(session: AsyncSession, payload: AccidentCreate) -> AccidentListItem:
    accident = Accident(
        id=_new_accident_id(),
        **payload.model_dump(),
        number_of_vehicles=0,
        number_of_casualties=0,
    )
    session.add(accident)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Invalid accident payload.") from exc

    query = (
        select(Accident)
        .options(
            joinedload(Accident.severity),
            joinedload(Accident.local_authority).joinedload(LocalAuthority.region),
        )
        .where(Accident.id == accident.id)
    )
    created = (await session.scalars(query)).first()
    if created is None:
        raise HTTPException(status_code=500, detail="Accident creation failed.")
    return _to_list_item(created)


async def patch_accident(
    session: AsyncSession,
    accident_id: str,
    payload: AccidentPatch,
) -> AccidentListItem:
    accident = await session.get(Accident, accident_id)
    if accident is None:
        raise HTTPException(status_code=404, detail="Accident not found.")

    updates = payload.model_dump(
        exclude_unset=True,
        exclude={"number_of_vehicles", "number_of_casualties"},
    )
    for field, value in updates.items():
        setattr(accident, field, value)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail="Invalid accident patch payload.") from exc

    query = (
        select(Accident)
        .options(
            joinedload(Accident.severity),
            joinedload(Accident.local_authority).joinedload(LocalAuthority.region),
        )
        .where(Accident.id == accident.id)
    )
    updated = (await session.scalars(query)).first()
    if updated is None:
        raise HTTPException(status_code=500, detail="Accident patch failed.")
    return _to_list_item(updated)


async def delete_accident(session: AsyncSession, accident_id: str) -> None:
    deleted_id = await session.scalar(
        delete(Accident).where(Accident.id == accident_id).returning(Accident.id)
    )
    if deleted_id is None:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Accident not found.")
    await session.commit()

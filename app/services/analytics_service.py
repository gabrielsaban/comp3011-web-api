from __future__ import annotations

from calendar import month_name
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Float, Integer, and_, case, cast, distinct, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.accident import Accident, Casualty, Vehicle
from app.models.lookups import (
    JunctionDetail,
    LightCondition,
    LocalAuthority,
    Region,
    RoadSurface,
    RoadType,
    VehicleType,
    WeatherCondition,
)
from app.models.weather import WeatherObservation
from app.schemas.analytics import (
    AccidentsByLocalAuthorityMeta,
    AccidentsByLocalAuthorityQuery,
    AccidentsByLocalAuthorityResponse,
    AccidentsByLocalAuthorityRow,
    AccidentsByTimePoint,
    AccidentsByTimeQuery,
    AccidentsByTimeResponse,
    AccidentsByVehicleTypeQuery,
    AccidentsByVehicleTypeResponse,
    AccidentsByVehicleTypeRow,
    AnnualTrendQuery,
    AnnualTrendResponse,
    AnnualTrendRow,
    CasualtiesByDemographicQuery,
    CasualtiesByDemographicResponse,
    CasualtiesByDemographicRow,
    DriverAgeSeverityQuery,
    DriverAgeSeverityResponse,
    DriverAgeSeverityRow,
    FatalConditionCombinationRow,
    FatalConditionCombinationsQuery,
    FatalConditionCombinationsResponse,
    LocalAuthorityAnalyticsRef,
    MultiVehicleSeverityQuery,
    MultiVehicleSeverityResponse,
    MultiVehicleSeverityRow,
    PoliceAttendanceProfileQuery,
    PoliceAttendanceProfileResponse,
    PoliceAttendanceProfileRow,
    SeasonalPatternQuery,
    SeasonalPatternResponse,
    SeasonalPatternRow,
    SeverityByConditionRow,
    SeverityByConditionsQuery,
    SeverityByConditionsResponse,
    SeverityByJourneyPurposeQuery,
    SeverityByJourneyPurposeResponse,
    SeverityByJourneyPurposeRow,
    SeverityBySpeedLimitQuery,
    SeverityBySpeedLimitResponse,
    SeverityBySpeedLimitRow,
    VulnerableRoadUsersQuery,
    VulnerableRoadUsersResponse,
    VulnerableRoadUsersRow,
)

DAY_LABELS = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
    7: "Saturday",
}

ALLOWED_CONDITION_DIMENSIONS = {
    "weather",
    "light",
    "road_surface",
    "road_type",
    "junction",
    "urban_or_rural",
    "precipitation_band",
    "visibility_band",
    "temperature_band",
}


def _round_pct(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100, 2)


def _apply_date_region_filters(
    query: Select[Any],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    region_id: int | None = None,
    local_authority_id: int | None = None,
) -> Select[Any]:
    if date_from is not None:
        query = query.where(Accident.date >= date_from)
    if date_to is not None:
        query = query.where(Accident.date <= date_to)
    if region_id is not None:
        query = query.where(Accident.local_authority.has(LocalAuthority.region_id == region_id))
    if local_authority_id is not None:
        query = query.where(Accident.local_authority_id == local_authority_id)
    return query


def _apply_year_filters(
    query: Select[Any],
    *,
    year_from: int | None,
    year_to: int | None,
) -> Select[Any]:
    year_expr: Any = cast(func.extract("year", Accident.date), Integer)
    if year_from is not None:
        query = query.where(year_expr >= year_from)
    if year_to is not None:
        query = query.where(year_expr <= year_to)
    return query


def _severity_counts() -> tuple[Any, Any, Any]:
    fatal = func.sum(case((Accident.severity_id == 1, 1), else_=0)).label("fatal")
    serious = func.sum(case((Accident.severity_id == 2, 1), else_=0)).label("serious")
    slight = func.sum(case((Accident.severity_id == 3, 1), else_=0)).label("slight")
    return fatal, serious, slight


def _driver_age_band_expr() -> Any:
    return case(
        (Vehicle.age_of_driver.is_(None), "Unknown"),
        (Vehicle.age_of_driver < 17, "Unknown"),
        (Vehicle.age_of_driver <= 24, "17-24"),
        (Vehicle.age_of_driver <= 34, "25-34"),
        (Vehicle.age_of_driver <= 44, "35-44"),
        (Vehicle.age_of_driver <= 54, "45-54"),
        (Vehicle.age_of_driver <= 64, "55-64"),
        else_="65+",
    )


def _midas_band_expr(dimension: str) -> Any:
    if dimension == "precipitation_band":
        return case(
            (WeatherObservation.precipitation_mm < 0.2, "Dry (<0.2mm)"),
            (
                and_(
                    WeatherObservation.precipitation_mm >= 0.2,
                    WeatherObservation.precipitation_mm <= 2.0,
                ),
                "Light (0.2-2mm)",
            ),
            (
                and_(
                    WeatherObservation.precipitation_mm > 2.0,
                    WeatherObservation.precipitation_mm <= 10.0,
                ),
                "Moderate (2-10mm)",
            ),
            else_="Heavy (>10mm)",
        )
    if dimension == "visibility_band":
        return case(
            (WeatherObservation.visibility_m < 100, "Dense Fog (<100m)"),
            (
                and_(
                    WeatherObservation.visibility_m >= 100, WeatherObservation.visibility_m <= 1000
                ),
                "Fog (100-1000m)",
            ),
            (
                and_(
                    WeatherObservation.visibility_m > 1000,
                    WeatherObservation.visibility_m <= 5000,
                ),
                "Mist (1000-5000m)",
            ),
            else_="Clear (>5000m)",
        )
    if dimension == "temperature_band":
        return case(
            (WeatherObservation.temperature_c <= 0, "Freezing (<=0C)"),
            (
                and_(WeatherObservation.temperature_c > 0, WeatherObservation.temperature_c <= 7),
                "Cold (0-7C)",
            ),
            (
                and_(WeatherObservation.temperature_c > 7, WeatherObservation.temperature_c <= 15),
                "Mild (7-15C)",
            ),
            else_="Warm (>15C)",
        )
    raise ValueError(f"Unsupported MIDAS dimension: {dimension}")


async def get_accidents_by_time(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    severity: int | None,
    region_id: int | None,
) -> AccidentsByTimeResponse:
    query: Select[Any] = select(
        Accident.day_of_week,
        cast(func.extract("hour", Accident.time), Integer).label("hour"),
        func.count(Accident.id).label("accident_count"),
    ).where(Accident.day_of_week.is_not(None), Accident.time.is_not(None))
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )
    if severity is not None:
        query = query.where(Accident.severity_id == severity)
    rows = (
        await session.execute(
            query.group_by(Accident.day_of_week, "hour").order_by(
                Accident.day_of_week.asc(), "hour"
            )
        )
    ).all()

    counts: dict[tuple[int, int], int] = {
        (day, hour): 0 for day in range(1, 8) for hour in range(24)
    }
    for row in rows:
        if row.day_of_week is None or row.hour is None:
            continue
        counts[(int(row.day_of_week), int(row.hour))] = int(row.accident_count)

    data = [
        AccidentsByTimePoint(
            hour=hour,
            day_of_week=day,
            day_label=DAY_LABELS[day],
            accident_count=counts[(day, hour)],
        )
        for day in range(1, 8)
        for hour in range(24)
    ]
    return AccidentsByTimeResponse(
        data=data,
        query=AccidentsByTimeQuery(
            date_from=date_from,
            date_to=date_to,
            severity=severity,
            region_id=region_id,
        ),
    )


async def get_annual_trend(
    session: AsyncSession,
    *,
    year_from: int | None,
    year_to: int | None,
    region_id: int | None,
    local_authority_id: int | None,
) -> AnnualTrendResponse:
    year_expr: Any = cast(func.extract("year", Accident.date), Integer)
    query = (
        select(
            year_expr.label("year"),
            func.count(distinct(Accident.id)).label("accidents"),
            func.count(Casualty.id).label("casualties"),
            func.sum(case((Casualty.severity_id == 1, 1), else_=0)).label("fatal_casualties"),
        )
        .select_from(Accident)
        .outerjoin(Casualty, Casualty.accident_id == Accident.id)
    )
    query = _apply_date_region_filters(
        query,
        region_id=region_id,
        local_authority_id=local_authority_id,
    )
    query = _apply_year_filters(query, year_from=year_from, year_to=year_to)
    rows = (await session.execute(query.group_by("year").order_by("year"))).all()

    data: list[AnnualTrendRow] = []
    previous_accidents: int | None = None
    for row in rows:
        accidents = int(row.accidents)
        change_pct: float | None = None
        if previous_accidents is not None and previous_accidents > 0:
            change_pct = round(((accidents - previous_accidents) / previous_accidents) * 100, 1)
        data.append(
            AnnualTrendRow(
                year=int(row.year),
                accidents=accidents,
                casualties=int(row.casualties or 0),
                fatal_casualties=int(row.fatal_casualties or 0),
                change_pct=change_pct,
            )
        )
        previous_accidents = accidents

    return AnnualTrendResponse(
        data=data,
        query=AnnualTrendQuery(
            year_from=year_from,
            year_to=year_to,
            region_id=region_id,
            local_authority_id=local_authority_id,
        ),
    )


async def get_severity_by_conditions(
    session: AsyncSession,
    *,
    dimension: str,
    date_from: date | None,
    date_to: date | None,
    region_id: int | None,
) -> SeverityByConditionsResponse:
    if dimension not in ALLOWED_CONDITION_DIMENSIONS:
        raise HTTPException(status_code=400, detail="Invalid dimension.")

    total_scope_query = select(func.count()).select_from(Accident)
    total_scope_query = _apply_date_region_filters(
        total_scope_query,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )
    total_scope = int((await session.scalar(total_scope_query)) or 0)

    fatal, serious, slight = _severity_counts()
    query = select(
        literal("Unknown").label("condition"),
        fatal,
        serious,
        slight,
        func.count(Accident.id).label("total"),
    ).select_from(Accident)
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )

    coverage_pct = 100.0
    if dimension == "weather":
        condition_expr = func.coalesce(WeatherCondition.label, "Unknown")
        query = query.outerjoin(
            WeatherCondition, Accident.weather_condition_id == WeatherCondition.id
        )
    elif dimension == "light":
        condition_expr = func.coalesce(LightCondition.label, "Unknown")
        query = query.outerjoin(LightCondition, Accident.light_condition_id == LightCondition.id)
    elif dimension == "road_surface":
        condition_expr = func.coalesce(RoadSurface.label, "Unknown")
        query = query.outerjoin(RoadSurface, Accident.road_surface_id == RoadSurface.id)
    elif dimension == "road_type":
        condition_expr = func.coalesce(RoadType.label, "Unknown")
        query = query.outerjoin(RoadType, Accident.road_type_id == RoadType.id)
    elif dimension == "junction":
        condition_expr = func.coalesce(JunctionDetail.label, "Unknown")
        query = query.outerjoin(JunctionDetail, Accident.junction_detail_id == JunctionDetail.id)
    elif dimension == "urban_or_rural":
        condition_expr = func.coalesce(Accident.urban_or_rural, "Unknown")
    else:
        condition_expr = _midas_band_expr(dimension)
        query = query.join(
            WeatherObservation, Accident.weather_observation_id == WeatherObservation.id
        )
        with_obs_query = select(func.count()).select_from(Accident)
        with_obs_query = _apply_date_region_filters(
            with_obs_query,
            date_from=date_from,
            date_to=date_to,
            region_id=region_id,
        ).where(Accident.weather_observation_id.is_not(None))
        covered = int((await session.scalar(with_obs_query)) or 0)
        coverage_pct = _round_pct(covered, total_scope)

    rows = (
        await session.execute(
            query.with_only_columns(
                condition_expr.label("condition"),
                fatal,
                serious,
                slight,
                func.count(Accident.id).label("total"),
            )
            .group_by("condition")
            .order_by(func.count(Accident.id).desc(), literal(1).asc())
        )
    ).all()
    data = [
        SeverityByConditionRow(
            condition=str(row.condition),
            fatal=int(row.fatal or 0),
            serious=int(row.serious or 0),
            slight=int(row.slight or 0),
            total=int(row.total),
            fatal_rate_pct=_round_pct(int(row.fatal or 0), int(row.total)),
        )
        for row in rows
    ]
    return SeverityByConditionsResponse(
        data=data,
        query=SeverityByConditionsQuery(
            dimension=dimension,
            date_from=date_from,
            date_to=date_to,
            region_id=region_id,
            # Kept under query to match docs/api-spec.md contract for this coursework.
            coverage_pct=coverage_pct,
        ),
    )


async def get_severity_by_speed_limit(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    urban_or_rural: str | None,
    region_id: int | None,
) -> SeverityBySpeedLimitResponse:
    fatal, serious, slight = _severity_counts()
    query = select(
        Accident.speed_limit,
        func.count(Accident.id).label("total_accidents"),
        fatal,
        serious,
        slight,
        func.avg(Accident.number_of_casualties).label("avg_casualties_per_accident"),
    ).where(Accident.speed_limit.is_not(None))
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )
    if urban_or_rural is not None:
        query = query.where(Accident.urban_or_rural == urban_or_rural)
    rows = (
        await session.execute(query.group_by(Accident.speed_limit).order_by(Accident.speed_limit))
    ).all()

    data = [
        SeverityBySpeedLimitRow(
            speed_limit=int(row.speed_limit),
            total_accidents=int(row.total_accidents),
            fatal=int(row.fatal or 0),
            serious=int(row.serious or 0),
            slight=int(row.slight or 0),
            fatal_rate_pct=_round_pct(int(row.fatal or 0), int(row.total_accidents)),
            avg_casualties_per_accident=round(float(row.avg_casualties_per_accident or 0.0), 2),
        )
        for row in rows
    ]
    return SeverityBySpeedLimitResponse(
        data=data,
        query=SeverityBySpeedLimitQuery(
            date_from=date_from,
            date_to=date_to,
            urban_or_rural=urban_or_rural,
            region_id=region_id,
        ),
    )


async def get_accidents_by_vehicle_type(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    region_id: int | None,
) -> AccidentsByVehicleTypeResponse:
    per_type_accident = (
        select(
            VehicleType.label.label("vehicle_type"),
            Accident.id.label("accident_id"),
            Accident.severity_id.label("severity_id"),
        )
        .join(Vehicle, Vehicle.vehicle_type_id == VehicleType.id)
        .join(Accident, Accident.id == Vehicle.accident_id)
        .group_by(VehicleType.label, Accident.id, Accident.severity_id)
    )
    per_type_accident = _apply_date_region_filters(
        per_type_accident,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )
    per_type_sq = per_type_accident.subquery()
    query = select(
        per_type_sq.c.vehicle_type,
        func.count(per_type_sq.c.accident_id).label("accidents_involved_in"),
        func.sum(case((per_type_sq.c.severity_id == 1, 1), else_=0)).label("fatal_count"),
        func.sum(case((per_type_sq.c.severity_id == 2, 1), else_=0)).label("serious_count"),
    ).group_by(per_type_sq.c.vehicle_type)
    rows = (
        await session.execute(
            query.order_by(
                func.count(per_type_sq.c.accident_id).desc(),
                per_type_sq.c.vehicle_type.asc(),
            )
        )
    ).all()
    data = [
        AccidentsByVehicleTypeRow(
            vehicle_type=str(row.vehicle_type),
            accidents_involved_in=int(row.accidents_involved_in),
            fatal_count=int(row.fatal_count or 0),
            serious_count=int(row.serious_count or 0),
            fatal_rate_pct=_round_pct(int(row.fatal_count or 0), int(row.accidents_involved_in)),
        )
        for row in rows
    ]
    return AccidentsByVehicleTypeResponse(
        data=data,
        query=AccidentsByVehicleTypeQuery(
            date_from=date_from,
            date_to=date_to,
            region_id=region_id,
        ),
    )


async def get_casualties_by_demographic(
    session: AsyncSession,
    *,
    severity: int | None,
    casualty_type: str | None,
    date_from: date | None,
    date_to: date | None,
) -> CasualtiesByDemographicResponse:
    query = select(
        func.coalesce(Casualty.age_band, "Unknown").label("age_band"),
        func.coalesce(Casualty.casualty_class, "Unknown").label("casualty_class"),
        func.coalesce(Casualty.sex, "Not known").label("sex"),
        func.count(Casualty.id).label("row_count"),
    ).join(Accident, Accident.id == Casualty.accident_id)
    query = _apply_date_region_filters(query, date_from=date_from, date_to=date_to)
    if severity is not None:
        query = query.where(Casualty.severity_id == severity)
    if casualty_type is not None:
        query = query.where(Casualty.casualty_type == casualty_type)
    rows = (
        await session.execute(
            query.group_by("age_band", "casualty_class", "sex").order_by(
                func.count(Casualty.id).desc()
            )
        )
    ).all()
    total = sum(int(row.row_count) for row in rows)
    data = [
        CasualtiesByDemographicRow(
            age_band=str(row.age_band),
            casualty_class=str(row.casualty_class),
            sex=str(row.sex),
            count=int(row.row_count),
            pct_of_total=_round_pct(int(row.row_count), total),
        )
        for row in rows
    ]
    return CasualtiesByDemographicResponse(
        data=data,
        query=CasualtiesByDemographicQuery(
            severity=severity,
            casualty_type=casualty_type,
            date_from=date_from,
            date_to=date_to,
        ),
    )


async def get_fatal_condition_combinations(
    session: AsyncSession,
    *,
    year_from: int | None,
    year_to: int | None,
    region_id: int | None,
    min_count: int,
    limit: int,
) -> FatalConditionCombinationsResponse:
    weather = func.coalesce(WeatherCondition.label, "Unknown").label("weather")
    light = func.coalesce(LightCondition.label, "Unknown").label("light")
    road_surface = func.coalesce(RoadSurface.label, "Unknown").label("road_surface")
    junction = func.coalesce(JunctionDetail.label, "Unknown").label("junction_detail")
    total = func.count(Accident.id).label("total_accidents")
    fatal = func.sum(case((Accident.severity_id == 1, 1), else_=0)).label("fatal_accidents")

    query = (
        select(weather, light, road_surface, junction, total, fatal)
        .select_from(Accident)
        .outerjoin(WeatherCondition, Accident.weather_condition_id == WeatherCondition.id)
        .outerjoin(LightCondition, Accident.light_condition_id == LightCondition.id)
        .outerjoin(RoadSurface, Accident.road_surface_id == RoadSurface.id)
        .outerjoin(JunctionDetail, Accident.junction_detail_id == JunctionDetail.id)
    )
    query = _apply_date_region_filters(query, region_id=region_id)
    query = _apply_year_filters(query, year_from=year_from, year_to=year_to)
    rows = (
        await session.execute(
            query.group_by("weather", "light", "road_surface", "junction_detail")
            .having(func.count(Accident.id) >= min_count)
            .order_by(
                (
                    cast(func.sum(case((Accident.severity_id == 1, 1), else_=0)), Float)
                    * 100
                    / func.count(Accident.id)
                ).desc(),
                func.count(Accident.id).desc(),
                weather.asc(),
                light.asc(),
                road_surface.asc(),
                junction.asc(),
            )
            .limit(limit)
        )
    ).all()

    data = [
        FatalConditionCombinationRow(
            rank=index + 1,
            weather=str(row.weather),
            light=str(row.light),
            road_surface=str(row.road_surface),
            junction_detail=str(row.junction_detail),
            total_accidents=int(row.total_accidents),
            fatal_accidents=int(row.fatal_accidents or 0),
            fatal_rate_pct=_round_pct(int(row.fatal_accidents or 0), int(row.total_accidents)),
        )
        for index, row in enumerate(rows)
    ]
    return FatalConditionCombinationsResponse(
        data=data,
        query=FatalConditionCombinationsQuery(
            year_from=year_from,
            year_to=year_to,
            region_id=region_id,
            min_count=min_count,
            limit=limit,
        ),
    )


async def get_accidents_by_local_authority(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    severity: int | None,
    region_id: int | None,
    limit: int,
) -> AccidentsByLocalAuthorityResponse:
    fatal, serious, _ = _severity_counts()
    query = (
        select(
            LocalAuthority.id.label("local_authority_id"),
            LocalAuthority.name.label("local_authority_name"),
            Region.name.label("region_name"),
            func.count(Accident.id).label("total_accidents"),
            fatal.label("fatal_accidents"),
            serious.label("serious_accidents"),
        )
        .select_from(Accident)
        .join(LocalAuthority, Accident.local_authority_id == LocalAuthority.id)
        .join(Region, LocalAuthority.region_id == Region.id)
    )
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )
    if severity is not None:
        query = query.where(Accident.severity_id == severity)
    grouped = query.group_by(LocalAuthority.id, LocalAuthority.name, Region.name)
    total_authorities = int(
        (
            await session.scalar(
                select(func.count()).select_from(
                    grouped.with_only_columns(LocalAuthority.id).subquery()
                )
            )
        )
        or 0
    )
    rows = (
        await session.execute(
            grouped.order_by(func.count(Accident.id).desc(), LocalAuthority.name.asc()).limit(limit)
        )
    ).all()
    data = [
        AccidentsByLocalAuthorityRow(
            local_authority=LocalAuthorityAnalyticsRef(
                id=int(row.local_authority_id),
                name=str(row.local_authority_name),
                region=str(row.region_name),
            ),
            total_accidents=int(row.total_accidents),
            fatal_accidents=int(row.fatal_accidents or 0),
            serious_accidents=int(row.serious_accidents or 0),
            fatal_rate_pct=_round_pct(int(row.fatal_accidents or 0), int(row.total_accidents)),
        )
        for row in rows
    ]
    return AccidentsByLocalAuthorityResponse(
        data=data,
        meta=AccidentsByLocalAuthorityMeta(total_authorities=total_authorities),
        query=AccidentsByLocalAuthorityQuery(
            date_from=date_from,
            date_to=date_to,
            severity=severity,
            region_id=region_id,
            limit=limit,
        ),
    )


async def get_severity_by_journey_purpose(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    vehicle_type_id: int | None,
    region_id: int | None,
) -> SeverityByJourneyPurposeResponse:
    per_purpose_accident = (
        select(
            func.coalesce(Vehicle.journey_purpose, "Unknown").label("journey_purpose"),
            Accident.id.label("accident_id"),
            Accident.severity_id.label("severity_id"),
        )
        .join(Accident, Accident.id == Vehicle.accident_id)
        .group_by("journey_purpose", Accident.id, Accident.severity_id)
    )
    per_purpose_accident = _apply_date_region_filters(
        per_purpose_accident,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )
    if vehicle_type_id is not None:
        per_purpose_accident = per_purpose_accident.where(
            Vehicle.vehicle_type_id == vehicle_type_id
        )
    per_purpose_sq = per_purpose_accident.subquery()
    query = select(
        per_purpose_sq.c.journey_purpose,
        func.count(per_purpose_sq.c.accident_id).label("total_accidents"),
        func.sum(case((per_purpose_sq.c.severity_id == 1, 1), else_=0)).label("fatal"),
        func.sum(case((per_purpose_sq.c.severity_id == 2, 1), else_=0)).label("serious"),
        func.sum(case((per_purpose_sq.c.severity_id == 3, 1), else_=0)).label("slight"),
    ).group_by(per_purpose_sq.c.journey_purpose)
    rows = (
        await session.execute(
            query.order_by(
                func.count(per_purpose_sq.c.accident_id).desc(),
                per_purpose_sq.c.journey_purpose.asc(),
            )
        )
    ).all()

    data = []
    for row in rows:
        total_accidents = int(row.total_accidents)
        fatal_count = int(row.fatal or 0)
        serious_count = int(row.serious or 0)
        data.append(
            SeverityByJourneyPurposeRow(
                journey_purpose=str(row.journey_purpose),
                total_accidents=total_accidents,
                fatal=fatal_count,
                serious=serious_count,
                slight=int(row.slight or 0),
                fatal_rate_pct=_round_pct(fatal_count, total_accidents),
                serious_or_fatal_rate_pct=_round_pct(fatal_count + serious_count, total_accidents),
            )
        )
    return SeverityByJourneyPurposeResponse(
        data=data,
        query=SeverityByJourneyPurposeQuery(
            date_from=date_from,
            date_to=date_to,
            vehicle_type_id=vehicle_type_id,
            region_id=region_id,
        ),
    )


async def get_seasonal_pattern(
    session: AsyncSession,
    *,
    year_from: int | None,
    year_to: int | None,
    region_id: int | None,
    urban_or_rural: str | None,
) -> SeasonalPatternResponse:
    month_expr: Any = cast(func.extract("month", Accident.date), Integer)
    query = select(
        month_expr.label("month"),
        func.count(Accident.id).label("total_accidents"),
        func.sum(case((Accident.severity_id == 1, 1), else_=0)).label("fatal_accidents"),
    )
    query = _apply_date_region_filters(query, region_id=region_id)
    query = _apply_year_filters(query, year_from=year_from, year_to=year_to)
    if urban_or_rural is not None:
        query = query.where(Accident.urban_or_rural == urban_or_rural)
    rows = (await session.execute(query.group_by("month").order_by("month"))).all()

    years_count = 0
    if year_from is not None and year_to is not None and year_to >= year_from:
        years_count = (year_to - year_from) + 1
    if years_count == 0:
        years_query = select(
            func.count(distinct(cast(func.extract("year", Accident.date), Integer)))
        )
        years_query = _apply_date_region_filters(years_query, region_id=region_id)
        years_query = _apply_year_filters(years_query, year_from=year_from, year_to=year_to)
        if urban_or_rural is not None:
            years_query = years_query.where(Accident.urban_or_rural == urban_or_rural)
        years_count = int((await session.scalar(years_query)) or 0)
    years_count = max(years_count, 1)

    data = []
    for row in rows:
        total_accidents = int(row.total_accidents)
        data.append(
            SeasonalPatternRow(
                month=int(row.month),
                month_label=month_name[int(row.month)],
                total_accidents=total_accidents,
                fatal_accidents=int(row.fatal_accidents or 0),
                fatal_rate_pct=_round_pct(int(row.fatal_accidents or 0), total_accidents),
                avg_accidents_per_year=round(total_accidents / years_count, 2),
            )
        )
    return SeasonalPatternResponse(
        data=data,
        query=SeasonalPatternQuery(
            year_from=year_from,
            year_to=year_to,
            region_id=region_id,
            urban_or_rural=urban_or_rural,
        ),
    )


async def get_driver_age_severity(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    vehicle_type_id: int | None,
    region_id: int | None,
) -> DriverAgeSeverityResponse:
    age_band = _driver_age_band_expr().label("age_band")
    per_age_accident = (
        select(
            age_band,
            Accident.id.label("accident_id"),
            Accident.severity_id.label("severity_id"),
        )
        .join(Accident, Accident.id == Vehicle.accident_id)
        .group_by(age_band, Accident.id, Accident.severity_id)
    )
    per_age_accident = _apply_date_region_filters(
        per_age_accident,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )
    if vehicle_type_id is not None:
        per_age_accident = per_age_accident.where(Vehicle.vehicle_type_id == vehicle_type_id)
    per_age_sq = per_age_accident.subquery()
    query = select(
        per_age_sq.c.age_band,
        func.count(per_age_sq.c.accident_id).label("total_accidents"),
        func.sum(case((per_age_sq.c.severity_id == 1, 1), else_=0)).label("fatal"),
        func.sum(case((per_age_sq.c.severity_id == 2, 1), else_=0)).label("serious"),
        func.sum(case((per_age_sq.c.severity_id == 3, 1), else_=0)).label("slight"),
    ).group_by(per_age_sq.c.age_band)
    rows = (
        await session.execute(query.order_by(func.count(per_age_sq.c.accident_id).desc()))
    ).all()

    data = []
    for row in rows:
        total_accidents = int(row.total_accidents)
        fatal_count = int(row.fatal or 0)
        serious_count = int(row.serious or 0)
        data.append(
            DriverAgeSeverityRow(
                age_band=str(row.age_band),
                total_accidents=total_accidents,
                fatal=fatal_count,
                serious=serious_count,
                slight=int(row.slight or 0),
                fatal_rate_pct=_round_pct(fatal_count, total_accidents),
                serious_or_fatal_rate_pct=_round_pct(fatal_count + serious_count, total_accidents),
            )
        )
    return DriverAgeSeverityResponse(
        data=data,
        query=DriverAgeSeverityQuery(
            date_from=date_from,
            date_to=date_to,
            vehicle_type_id=vehicle_type_id,
            region_id=region_id,
        ),
    )


async def get_vulnerable_road_users(
    session: AsyncSession,
    *,
    casualty_type: str | None,
    date_from: date | None,
    date_to: date | None,
    region_id: int | None,
) -> VulnerableRoadUsersResponse:
    query = (
        select(
            Accident.speed_limit,
            Accident.urban_or_rural,
            func.count(Casualty.id).label("total_casualties"),
            func.sum(case((Casualty.severity_id == 1, 1), else_=0)).label("fatal_casualties"),
            func.sum(case((Casualty.severity_id == 2, 1), else_=0)).label("serious_casualties"),
        )
        .select_from(Casualty)
        .join(Accident, Accident.id == Casualty.accident_id)
        .where(Accident.speed_limit.is_not(None), Accident.urban_or_rural.is_not(None))
    )
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )
    if casualty_type is not None:
        query = query.where(Casualty.casualty_type == casualty_type)
    else:
        query = query.where(Casualty.casualty_type.in_(("Pedestrian", "Cyclist")))
    rows = (
        await session.execute(
            query.group_by(Accident.speed_limit, Accident.urban_or_rural).order_by(
                Accident.speed_limit.asc(),
                Accident.urban_or_rural.asc(),
            )
        )
    ).all()
    data = [
        VulnerableRoadUsersRow(
            speed_limit=int(row.speed_limit),
            urban_or_rural=str(row.urban_or_rural),
            total_casualties=int(row.total_casualties),
            fatal_casualties=int(row.fatal_casualties or 0),
            serious_casualties=int(row.serious_casualties or 0),
            fatal_rate_pct=_round_pct(int(row.fatal_casualties or 0), int(row.total_casualties)),
        )
        for row in rows
    ]
    return VulnerableRoadUsersResponse(
        data=data,
        query=VulnerableRoadUsersQuery(
            casualty_type=casualty_type,
            date_from=date_from,
            date_to=date_to,
            region_id=region_id,
        ),
    )


async def get_police_attendance_profile(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    region_id: int | None,
) -> PoliceAttendanceProfileResponse:
    fatal, serious, slight = _severity_counts()
    query = (
        select(
            Accident.police_attended,
            func.count(Accident.id).label("total_accidents"),
            fatal,
            serious,
            slight,
        )
        .where(Accident.police_attended.is_not(None))
        .group_by(Accident.police_attended)
    )
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )
    rows = (await session.execute(query.order_by(Accident.police_attended.desc()))).all()
    data = []
    for row in rows:
        total_accidents = int(row.total_accidents)
        fatal_count = int(row.fatal or 0)
        serious_count = int(row.serious or 0)
        data.append(
            PoliceAttendanceProfileRow(
                police_attended=bool(row.police_attended),
                total_accidents=total_accidents,
                fatal=fatal_count,
                serious=serious_count,
                slight=int(row.slight or 0),
                fatal_rate_pct=_round_pct(fatal_count, total_accidents),
                serious_or_fatal_rate_pct=_round_pct(fatal_count + serious_count, total_accidents),
            )
        )
    return PoliceAttendanceProfileResponse(
        data=data,
        query=PoliceAttendanceProfileQuery(
            date_from=date_from,
            date_to=date_to,
            region_id=region_id,
        ),
    )


async def get_multi_vehicle_severity(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    group_by_speed_limit: bool,
    region_id: int | None,
) -> MultiVehicleSeverityResponse:
    collision_type = case(
        (Accident.number_of_vehicles > 1, "Multi vehicle"),
        else_="Single vehicle",
    ).label("collision_type")
    speed_expr: Any
    group_fields: list[Any]
    order_fields: list[Any]

    if group_by_speed_limit:
        speed_expr = Accident.speed_limit.label("speed_limit")
        group_fields = [collision_type, Accident.speed_limit]
        order_fields = [collision_type.asc(), Accident.speed_limit.asc()]
    else:
        speed_expr = cast(literal(None), Integer).label("speed_limit")
        group_fields = [collision_type]
        order_fields = [collision_type.asc()]

    fatal, serious, slight = _severity_counts()
    query = select(
        collision_type,
        speed_expr,
        func.count(Accident.id).label("total_accidents"),
        fatal,
        serious,
        slight,
        func.avg(Accident.number_of_casualties).label("avg_casualties_per_accident"),
    )
    query = _apply_date_region_filters(
        query, date_from=date_from, date_to=date_to, region_id=region_id
    )
    rows = (await session.execute(query.group_by(*group_fields).order_by(*order_fields))).all()

    data = [
        MultiVehicleSeverityRow(
            collision_type=str(row.collision_type),
            speed_limit=int(row.speed_limit) if row.speed_limit is not None else None,
            total_accidents=int(row.total_accidents),
            fatal=int(row.fatal or 0),
            serious=int(row.serious or 0),
            slight=int(row.slight or 0),
            fatal_rate_pct=_round_pct(int(row.fatal or 0), int(row.total_accidents)),
            avg_casualties_per_accident=round(float(row.avg_casualties_per_accident or 0.0), 2),
        )
        for row in rows
    ]
    return MultiVehicleSeverityResponse(
        data=data,
        query=MultiVehicleSeverityQuery(
            date_from=date_from,
            date_to=date_to,
            group_by_speed_limit=group_by_speed_limit,
            region_id=region_id,
        ),
    )

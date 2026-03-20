from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas.analytics import (
    AccidentsByLocalAuthorityResponse,
    AccidentsByTimeResponse,
    AccidentsByVehicleTypeResponse,
    AnnualTrendResponse,
    CasualtiesByDemographicResponse,
    DriverAgeSeverityResponse,
    FatalConditionCombinationsResponse,
    HotspotsResponse,
    MultiVehicleSeverityResponse,
    PoliceAttendanceProfileResponse,
    SeasonalPatternResponse,
    SeverityByConditionsResponse,
    SeverityByJourneyPurposeResponse,
    SeverityBySpeedLimitResponse,
    VulnerableRoadUsersResponse,
    WeatherCorrelationResponse,
)
from app.services.analytics_service import (
    get_accidents_by_local_authority,
    get_accidents_by_time,
    get_accidents_by_vehicle_type,
    get_annual_trend,
    get_casualties_by_demographic,
    get_driver_age_severity,
    get_fatal_condition_combinations,
    get_hotspots,
    get_multi_vehicle_severity,
    get_police_attendance_profile,
    get_seasonal_pattern,
    get_severity_by_conditions,
    get_severity_by_journey_purpose,
    get_severity_by_speed_limit,
    get_vulnerable_road_users,
    get_weather_correlation,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/accidents-by-time", response_model=AccidentsByTimeResponse)
async def accidents_by_time(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    severity: int | None = None,
    region_id: int | None = None,
) -> AccidentsByTimeResponse:
    return await get_accidents_by_time(
        db,
        date_from=date_from,
        date_to=date_to,
        severity=severity,
        region_id=region_id,
    )


@router.get("/annual-trend", response_model=AnnualTrendResponse)
async def annual_trend(
    db: DbSession,
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
    region_id: int | None = None,
    local_authority_id: int | None = None,
) -> AnnualTrendResponse:
    return await get_annual_trend(
        db,
        year_from=year_from,
        year_to=year_to,
        region_id=region_id,
        local_authority_id=local_authority_id,
    )


@router.get("/severity-by-conditions", response_model=SeverityByConditionsResponse)
async def severity_by_conditions(
    db: DbSession,
    dimension: str = Query(
        pattern="^(weather|light|road_surface|road_type|junction|urban_or_rural|precipitation_band|visibility_band|temperature_band)$"
    ),
    date_from: date | None = None,
    date_to: date | None = None,
    region_id: int | None = None,
) -> SeverityByConditionsResponse:
    return await get_severity_by_conditions(
        db,
        dimension=dimension,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )


@router.get("/severity-by-speed-limit", response_model=SeverityBySpeedLimitResponse)
async def severity_by_speed_limit(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    urban_or_rural: str | None = Query(default=None, pattern="^(Urban|Rural|Unallocated)$"),
    region_id: int | None = None,
) -> SeverityBySpeedLimitResponse:
    return await get_severity_by_speed_limit(
        db,
        date_from=date_from,
        date_to=date_to,
        urban_or_rural=urban_or_rural,
        region_id=region_id,
    )


@router.get("/accidents-by-vehicle-type", response_model=AccidentsByVehicleTypeResponse)
async def accidents_by_vehicle_type(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    region_id: int | None = None,
) -> AccidentsByVehicleTypeResponse:
    return await get_accidents_by_vehicle_type(
        db,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )


@router.get("/hotspots", response_model=HotspotsResponse)
async def hotspots(
    db: DbSession,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=5.0, gt=0),
    severity: int | None = Query(default=None, ge=1, le=3),
    date_from: date | None = None,
    date_to: date | None = None,
) -> HotspotsResponse:
    return await get_hotspots(
        db,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/casualties-by-demographic", response_model=CasualtiesByDemographicResponse)
async def casualties_by_demographic(
    db: DbSession,
    severity: int | None = None,
    casualty_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> CasualtiesByDemographicResponse:
    return await get_casualties_by_demographic(
        db,
        severity=severity,
        casualty_type=casualty_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/fatal-condition-combinations", response_model=FatalConditionCombinationsResponse)
async def fatal_condition_combinations(
    db: DbSession,
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
    region_id: int | None = None,
    min_count: int = Query(default=10, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
) -> FatalConditionCombinationsResponse:
    return await get_fatal_condition_combinations(
        db,
        year_from=year_from,
        year_to=year_to,
        region_id=region_id,
        min_count=min_count,
        limit=limit,
    )


@router.get("/weather-correlation", response_model=WeatherCorrelationResponse)
async def weather_correlation(
    db: DbSession,
    metric: str = Query(pattern="^(precipitation|visibility|temperature|wind_speed)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    region_id: int | None = None,
) -> WeatherCorrelationResponse:
    return await get_weather_correlation(
        db,
        metric=metric,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )


@router.get("/accidents-by-local-authority", response_model=AccidentsByLocalAuthorityResponse)
async def accidents_by_local_authority(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    severity: int | None = None,
    region_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=500),
) -> AccidentsByLocalAuthorityResponse:
    return await get_accidents_by_local_authority(
        db,
        date_from=date_from,
        date_to=date_to,
        severity=severity,
        region_id=region_id,
        limit=limit,
    )


@router.get("/severity-by-journey-purpose", response_model=SeverityByJourneyPurposeResponse)
async def severity_by_journey_purpose(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    vehicle_type_id: int | None = None,
    region_id: int | None = None,
) -> SeverityByJourneyPurposeResponse:
    return await get_severity_by_journey_purpose(
        db,
        date_from=date_from,
        date_to=date_to,
        vehicle_type_id=vehicle_type_id,
        region_id=region_id,
    )


@router.get("/seasonal-pattern", response_model=SeasonalPatternResponse)
async def seasonal_pattern(
    db: DbSession,
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
    region_id: int | None = None,
    urban_or_rural: str | None = Query(default=None, pattern="^(Urban|Rural|Unallocated)$"),
) -> SeasonalPatternResponse:
    return await get_seasonal_pattern(
        db,
        year_from=year_from,
        year_to=year_to,
        region_id=region_id,
        urban_or_rural=urban_or_rural,
    )


@router.get("/driver-age-severity", response_model=DriverAgeSeverityResponse)
async def driver_age_severity(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    vehicle_type_id: int | None = None,
    region_id: int | None = None,
) -> DriverAgeSeverityResponse:
    return await get_driver_age_severity(
        db,
        date_from=date_from,
        date_to=date_to,
        vehicle_type_id=vehicle_type_id,
        region_id=region_id,
    )


@router.get("/vulnerable-road-users", response_model=VulnerableRoadUsersResponse)
async def vulnerable_road_users(
    db: DbSession,
    casualty_type: str | None = Query(default=None, pattern="^(Pedestrian|Cyclist)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    region_id: int | None = None,
) -> VulnerableRoadUsersResponse:
    return await get_vulnerable_road_users(
        db,
        casualty_type=casualty_type,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )


@router.get("/police-attendance-profile", response_model=PoliceAttendanceProfileResponse)
async def police_attendance_profile(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    region_id: int | None = None,
) -> PoliceAttendanceProfileResponse:
    return await get_police_attendance_profile(
        db,
        date_from=date_from,
        date_to=date_to,
        region_id=region_id,
    )


@router.get("/multi-vehicle-severity", response_model=MultiVehicleSeverityResponse)
async def multi_vehicle_severity(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    group_by_speed_limit: bool = False,
    region_id: int | None = None,
) -> MultiVehicleSeverityResponse:
    return await get_multi_vehicle_severity(
        db,
        date_from=date_from,
        date_to=date_to,
        group_by_speed_limit=group_by_speed_limit,
        region_id=region_id,
    )

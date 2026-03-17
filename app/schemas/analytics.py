from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class AccidentsByTimePoint(BaseModel):
    hour: int
    day_of_week: int
    day_label: str
    accident_count: int


class AccidentsByTimeQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    severity: int | None
    region_id: int | None


class AccidentsByTimeResponse(BaseModel):
    data: list[AccidentsByTimePoint]
    query: AccidentsByTimeQuery


class AnnualTrendRow(BaseModel):
    year: int
    accidents: int
    casualties: int
    fatal_casualties: int
    change_pct: float | None


class AnnualTrendQuery(BaseModel):
    year_from: int | None
    year_to: int | None
    region_id: int | None
    local_authority_id: int | None


class AnnualTrendResponse(BaseModel):
    data: list[AnnualTrendRow]
    query: AnnualTrendQuery


class SeverityByConditionRow(BaseModel):
    condition: str
    fatal: int
    serious: int
    slight: int
    total: int
    fatal_rate_pct: float


class SeverityByConditionsQuery(BaseModel):
    dimension: str
    date_from: date | None
    date_to: date | None
    region_id: int | None
    coverage_pct: float


class SeverityByConditionsResponse(BaseModel):
    data: list[SeverityByConditionRow]
    query: SeverityByConditionsQuery


class SeverityBySpeedLimitRow(BaseModel):
    speed_limit: int
    total_accidents: int
    fatal: int
    serious: int
    slight: int
    fatal_rate_pct: float
    avg_casualties_per_accident: float


class SeverityBySpeedLimitQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    urban_or_rural: str | None
    region_id: int | None


class SeverityBySpeedLimitResponse(BaseModel):
    data: list[SeverityBySpeedLimitRow]
    query: SeverityBySpeedLimitQuery


class AccidentsByVehicleTypeRow(BaseModel):
    vehicle_type: str
    accidents_involved_in: int
    fatal_count: int
    serious_count: int
    fatal_rate_pct: float


class AccidentsByVehicleTypeQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    region_id: int | None


class AccidentsByVehicleTypeResponse(BaseModel):
    data: list[AccidentsByVehicleTypeRow]
    query: AccidentsByVehicleTypeQuery


class CasualtiesByDemographicRow(BaseModel):
    age_band: str
    casualty_class: str
    sex: str
    count: int
    pct_of_total: float


class CasualtiesByDemographicQuery(BaseModel):
    severity: int | None
    casualty_type: str | None
    date_from: date | None
    date_to: date | None


class CasualtiesByDemographicResponse(BaseModel):
    data: list[CasualtiesByDemographicRow]
    query: CasualtiesByDemographicQuery


class FatalConditionCombinationRow(BaseModel):
    rank: int
    weather: str
    light: str
    road_surface: str
    junction_detail: str
    total_accidents: int
    fatal_accidents: int
    fatal_rate_pct: float


class FatalConditionCombinationsQuery(BaseModel):
    year_from: int | None
    year_to: int | None
    region_id: int | None
    min_count: int
    limit: int


class FatalConditionCombinationsResponse(BaseModel):
    data: list[FatalConditionCombinationRow]
    query: FatalConditionCombinationsQuery


class LocalAuthorityAnalyticsRef(BaseModel):
    id: int
    name: str
    region: str


class AccidentsByLocalAuthorityRow(BaseModel):
    local_authority: LocalAuthorityAnalyticsRef
    total_accidents: int
    fatal_accidents: int
    serious_accidents: int
    fatal_rate_pct: float


class AccidentsByLocalAuthorityMeta(BaseModel):
    total_authorities: int


class AccidentsByLocalAuthorityQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    severity: int | None
    region_id: int | None
    limit: int


class AccidentsByLocalAuthorityResponse(BaseModel):
    data: list[AccidentsByLocalAuthorityRow]
    meta: AccidentsByLocalAuthorityMeta
    query: AccidentsByLocalAuthorityQuery


class SeverityByJourneyPurposeRow(BaseModel):
    journey_purpose: str
    total_accidents: int
    fatal: int
    serious: int
    slight: int
    fatal_rate_pct: float
    serious_or_fatal_rate_pct: float


class SeverityByJourneyPurposeQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    vehicle_type_id: int | None
    region_id: int | None


class SeverityByJourneyPurposeResponse(BaseModel):
    data: list[SeverityByJourneyPurposeRow]
    query: SeverityByJourneyPurposeQuery


class SeasonalPatternRow(BaseModel):
    month: int
    month_label: str
    total_accidents: int
    fatal_accidents: int
    fatal_rate_pct: float
    avg_accidents_per_year: float


class SeasonalPatternQuery(BaseModel):
    year_from: int | None
    year_to: int | None
    region_id: int | None
    urban_or_rural: str | None


class SeasonalPatternResponse(BaseModel):
    data: list[SeasonalPatternRow]
    query: SeasonalPatternQuery


class DriverAgeSeverityRow(BaseModel):
    age_band: str
    total_accidents: int
    fatal: int
    serious: int
    slight: int
    fatal_rate_pct: float
    serious_or_fatal_rate_pct: float


class DriverAgeSeverityQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    vehicle_type_id: int | None
    region_id: int | None


class DriverAgeSeverityResponse(BaseModel):
    data: list[DriverAgeSeverityRow]
    query: DriverAgeSeverityQuery


class VulnerableRoadUsersRow(BaseModel):
    speed_limit: int
    urban_or_rural: str
    total_casualties: int
    fatal_casualties: int
    serious_casualties: int
    fatal_rate_pct: float


class VulnerableRoadUsersQuery(BaseModel):
    casualty_type: str | None
    date_from: date | None
    date_to: date | None
    region_id: int | None


class VulnerableRoadUsersResponse(BaseModel):
    data: list[VulnerableRoadUsersRow]
    query: VulnerableRoadUsersQuery


class PoliceAttendanceProfileRow(BaseModel):
    police_attended: bool
    total_accidents: int
    fatal: int
    serious: int
    slight: int
    fatal_rate_pct: float
    serious_or_fatal_rate_pct: float


class PoliceAttendanceProfileQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    region_id: int | None


class PoliceAttendanceProfileResponse(BaseModel):
    data: list[PoliceAttendanceProfileRow]
    query: PoliceAttendanceProfileQuery


class MultiVehicleSeverityRow(BaseModel):
    collision_type: str
    speed_limit: int | None
    total_accidents: int
    fatal: int
    serious: int
    slight: int
    fatal_rate_pct: float
    avg_casualties_per_accident: float


class MultiVehicleSeverityQuery(BaseModel):
    date_from: date | None
    date_to: date | None
    group_by_speed_limit: bool
    region_id: int | None


class MultiVehicleSeverityResponse(BaseModel):
    data: list[MultiVehicleSeverityRow]
    query: MultiVehicleSeverityQuery

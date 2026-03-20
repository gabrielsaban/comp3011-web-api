from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.route_risk_constants import (
    DEFAULT_BUFFER_RADIUS_KM,
    DEFAULT_SEGMENT_LENGTH_KM,
    MAX_BUFFER_RADIUS_KM,
    MAX_SEGMENT_LENGTH_KM,
    MIN_BUFFER_RADIUS_KM,
    MIN_SEGMENT_LENGTH_KM,
)


class RouteRiskOptions(BaseModel):
    time_of_day: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    day_of_week: int | None = Field(default=None, ge=1, le=7)
    segment_length_km: float = Field(
        default=DEFAULT_SEGMENT_LENGTH_KM,
        ge=MIN_SEGMENT_LENGTH_KM,
        le=MAX_SEGMENT_LENGTH_KM,
    )
    buffer_radius_km: float = Field(
        default=DEFAULT_BUFFER_RADIUS_KM,
        ge=MIN_BUFFER_RADIUS_KM,
        le=MAX_BUFFER_RADIUS_KM,
    )


class RouteRiskRequest(BaseModel):
    waypoints: list[tuple[float, float]] = Field(min_length=2, max_length=500)
    options: RouteRiskOptions | None = None

    @field_validator("waypoints")
    @classmethod
    def validate_waypoints(cls, value: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for lat, lng in value:
            if not (-90 <= lat <= 90):
                raise ValueError("Waypoint latitude must be between -90 and 90.")
            if not (-180 <= lng <= 180):
                raise ValueError("Waypoint longitude must be between -180 and 180.")
        return value


class RouteRiskFactors(BaseModel):
    accident_density: float
    severity_score: float
    time_risk: float
    speed_limit_risk: float
    cluster_proximity: float


class RouteRiskSegment(BaseModel):
    segment_id: int
    start: tuple[float, float]
    end: tuple[float, float]
    length_km: float
    risk_score: float
    risk_label: str
    factors: RouteRiskFactors
    nearby_accidents: int
    nearby_cluster_ids: list[int]
    dominant_speed_limit: int | None


class RouteSummary(BaseModel):
    total_distance_km: float
    segment_count: int
    aggregate_risk_score: float
    risk_label: str
    peak_segment_risk: float
    peak_segment_id: int
    clusters_intersected: int


class RouteRiskData(BaseModel):
    route_summary: RouteSummary
    segments: list[RouteRiskSegment]


class RouteRiskQuery(BaseModel):
    waypoint_count: int
    segment_length_km: float
    buffer_radius_km: float
    time_of_day: str
    day_of_week: int


class RouteRiskResponse(BaseModel):
    data: RouteRiskData
    query: RouteRiskQuery


class RouteRiskScoringModelData(BaseModel):
    formula: str
    weights: dict[str, float]
    factor_descriptions: dict[str, str]
    risk_labels: dict[str, str]


class RouteRiskScoringModelResponse(BaseModel):
    data: RouteRiskScoringModelData

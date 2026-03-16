from __future__ import annotations

from pydantic import BaseModel

from app.schemas.accident import AccidentListItem, MetaPagination, NamedRef


class ClusterListItem(BaseModel):
    id: int
    centroid_lat: float
    centroid_lng: float
    radius_km: float
    accident_count: int
    fatal_count: int
    serious_count: int
    fatal_rate_pct: float
    severity_label: str
    local_authority: NamedRef | None


class ClusterCollectionResponse(BaseModel):
    data: list[ClusterListItem]
    meta: MetaPagination


class ClusterBBox(BaseModel):
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float


class DominantConditions(BaseModel):
    weather: str | None
    light: str | None
    road_surface: str | None
    speed_limit: int | None


class AnnualTrendPoint(BaseModel):
    year: int
    accident_count: int


class ClusterDetail(ClusterListItem):
    bbox: ClusterBBox
    dominant_conditions: DominantConditions
    annual_trend: list[AnnualTrendPoint]


class ClusterItemResponse(BaseModel):
    data: ClusterDetail


class ClusterAccidentContext(BaseModel):
    id: int
    centroid_lat: float
    centroid_lng: float
    severity_label: str


class ClusterAccidentCollectionResponse(BaseModel):
    context: ClusterAccidentContext
    data: list[AccidentListItem]
    meta: MetaPagination

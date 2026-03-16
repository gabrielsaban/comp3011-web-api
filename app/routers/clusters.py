from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas.cluster import (
    ClusterAccidentCollectionResponse,
    ClusterCollectionResponse,
    ClusterItemResponse,
)
from app.services.cluster_service import (
    build_cluster_scoped_filters,
    get_cluster,
    list_cluster_accidents,
    list_clusters,
)

router = APIRouter(prefix="/api/v1/clusters", tags=["Clusters"])


@router.get("", response_model=ClusterCollectionResponse)
async def get_clusters(
    db: DbSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    region_id: int | None = None,
    min_accidents: int = Query(default=10, ge=1),
    severity_label: str | None = None,
) -> ClusterCollectionResponse:
    data, meta = await list_clusters(
        db,
        page=page,
        per_page=per_page,
        region_id=region_id,
        min_accidents=min_accidents,
        severity_label=severity_label,
    )
    return ClusterCollectionResponse(data=data, meta=meta)


@router.get("/{cluster_id}", response_model=ClusterItemResponse)
async def get_cluster_by_id(cluster_id: int, db: DbSession) -> ClusterItemResponse:
    return ClusterItemResponse(data=await get_cluster(db, cluster_id))


@router.get("/{cluster_id}/accidents", response_model=ClusterAccidentCollectionResponse)
async def get_cluster_accidents(
    cluster_id: int,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="date", pattern="^(date|severity)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    severity: int | None = None,
    region_id: int | None = None,
    local_authority_id: int | None = None,
    road_type_id: int | None = None,
    weather_condition_id: int | None = None,
    light_condition_id: int | None = None,
    speed_limit: int | None = None,
    urban_or_rural: str | None = Query(default=None, pattern="^(Urban|Rural|Unallocated)$"),
) -> ClusterAccidentCollectionResponse:
    filters = build_cluster_scoped_filters(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        date_from=date_from,
        date_to=date_to,
        severity=severity,
        region_id=region_id,
        local_authority_id=local_authority_id,
        road_type_id=road_type_id,
        weather_condition_id=weather_condition_id,
        light_condition_id=light_condition_id,
        speed_limit=speed_limit,
        urban_or_rural=urban_or_rural,
    )
    context, data, meta = await list_cluster_accidents(db, cluster_id, filters)
    return ClusterAccidentCollectionResponse(context=context, data=data, meta=meta)

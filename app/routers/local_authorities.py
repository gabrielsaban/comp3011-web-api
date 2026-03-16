from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas.relationship import LocalAuthorityAccidentCollectionResponse
from app.services.relationship_service import (
    build_scoped_accident_filters,
    list_local_authority_accidents,
)

router = APIRouter(
    prefix="/api/v1/local-authorities",
    tags=["Relationships"],
)


@router.get(
    "/{local_authority_id}/accidents",
    response_model=LocalAuthorityAccidentCollectionResponse,
)
async def get_local_authority_accidents(
    local_authority_id: int,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="date", pattern="^(date|severity)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    severity: int | None = None,
    region_id: int | None = None,
    road_type_id: int | None = None,
    weather_condition_id: int | None = None,
    light_condition_id: int | None = None,
    speed_limit: int | None = None,
    urban_or_rural: str | None = Query(default=None, pattern="^(Urban|Rural|Unallocated)$"),
    cluster_id: int | None = None,
) -> LocalAuthorityAccidentCollectionResponse:
    filters = build_scoped_accident_filters(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        date_from=date_from,
        date_to=date_to,
        severity=severity,
        region_id=region_id,
        road_type_id=road_type_id,
        weather_condition_id=weather_condition_id,
        light_condition_id=light_condition_id,
        speed_limit=speed_limit,
        urban_or_rural=urban_or_rural,
        cluster_id=cluster_id,
    )
    context, data, meta = await list_local_authority_accidents(db, local_authority_id, filters)
    return LocalAuthorityAccidentCollectionResponse(context=context, data=data, meta=meta)

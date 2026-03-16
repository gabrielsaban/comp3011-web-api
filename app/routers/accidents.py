from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Response, status

from app.dependencies import AdminUser, DbSession, EditorUser
from app.schemas.accident import (
    AccidentCollectionResponse,
    AccidentCreate,
    AccidentDetailResponse,
    AccidentListResponse,
    AccidentPatch,
    MetaPagination,
)
from app.services.accident_service import (
    AccidentListFilters,
    create_accident,
    delete_accident,
    get_accident_detail,
    list_accidents,
    patch_accident,
)

router = APIRouter(prefix="/api/v1/accidents", tags=["Accidents"])


@router.get("", response_model=AccidentCollectionResponse)
async def get_accidents(
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
    cluster_id: int | None = None,
) -> AccidentCollectionResponse:
    filters = AccidentListFilters(
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
        cluster_id=cluster_id,
    )
    data, total = await list_accidents(db, filters)
    return AccidentCollectionResponse(
        data=data,
        meta=MetaPagination(page=page, per_page=per_page, total=total),
    )


@router.get("/{accident_id}", response_model=AccidentDetailResponse)
async def get_accident(accident_id: str, db: DbSession) -> AccidentDetailResponse:
    return AccidentDetailResponse(data=await get_accident_detail(db, accident_id))


@router.post("", response_model=AccidentListResponse, status_code=status.HTTP_201_CREATED)
async def post_accident(
    body: AccidentCreate,
    db: DbSession,
    user: EditorUser,
) -> AccidentListResponse:
    return AccidentListResponse(data=await create_accident(db, body))


@router.patch("/{accident_id}", response_model=AccidentListResponse)
async def patch_accident_route(
    accident_id: str,
    body: AccidentPatch,
    db: DbSession,
    user: EditorUser,
) -> AccidentListResponse:
    return AccidentListResponse(data=await patch_accident(db, accident_id, body))


@router.delete("/{accident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_accident_route(accident_id: str, db: DbSession, user: AdminUser) -> Response:
    await delete_accident(db, accident_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

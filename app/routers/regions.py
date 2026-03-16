from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DbSession
from app.schemas.relationship import (
    RegionCollectionResponse,
    RegionItemResponse,
    RegionLocalAuthorityCollectionResponse,
)
from app.services.relationship_service import (
    get_region,
    list_region_local_authorities,
    list_regions,
)

router = APIRouter(prefix="/api/v1/regions", tags=["Relationships"])


@router.get("", response_model=RegionCollectionResponse)
async def get_regions(db: DbSession) -> RegionCollectionResponse:
    return RegionCollectionResponse(data=await list_regions(db))


@router.get("/{region_id}", response_model=RegionItemResponse)
async def get_region_by_id(region_id: int, db: DbSession) -> RegionItemResponse:
    return RegionItemResponse(data=await get_region(db, region_id))


@router.get("/{region_id}/local-authorities", response_model=RegionLocalAuthorityCollectionResponse)
async def get_region_local_authorities(
    region_id: int,
    db: DbSession,
) -> RegionLocalAuthorityCollectionResponse:
    context, data = await list_region_local_authorities(db, region_id)
    return RegionLocalAuthorityCollectionResponse(context=context, data=data)

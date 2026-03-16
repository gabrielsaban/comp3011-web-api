from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.lookups import LocalAuthority, Region
from app.schemas.accident import AccidentListItem, MetaPagination, NamedRef
from app.schemas.relationship import LocalAuthorityContext, RegionContext, RegionSummary
from app.services.accident_service import AccidentListFilters, list_accidents


async def list_regions(session: AsyncSession) -> list[RegionSummary]:
    rows = (
        await session.execute(
            select(
                Region.id,
                Region.name,
                func.count(LocalAuthority.id).label("local_authority_count"),
            )
            .outerjoin(LocalAuthority, LocalAuthority.region_id == Region.id)
            .group_by(Region.id, Region.name)
            .order_by(Region.name.asc())
        )
    ).all()
    return [
        RegionSummary(
            id=row.id,
            name=row.name,
            local_authority_count=int(row.local_authority_count),
        )
        for row in rows
    ]


async def get_region(session: AsyncSession, region_id: int) -> RegionSummary:
    row = (
        await session.execute(
            select(
                Region.id,
                Region.name,
                func.count(LocalAuthority.id).label("local_authority_count"),
            )
            .outerjoin(LocalAuthority, LocalAuthority.region_id == Region.id)
            .where(Region.id == region_id)
            .group_by(Region.id, Region.name)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Region not found.")
    return RegionSummary(
        id=row.id,
        name=row.name,
        local_authority_count=int(row.local_authority_count),
    )


async def list_region_local_authorities(
    session: AsyncSession,
    region_id: int,
) -> tuple[RegionContext, list[NamedRef]]:
    region = await session.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found.")

    rows = (
        await session.execute(
            select(LocalAuthority.id, LocalAuthority.name)
            .where(LocalAuthority.region_id == region_id)
            .order_by(LocalAuthority.name.asc())
        )
    ).all()
    return (
        RegionContext(id=region.id, name=region.name),
        [NamedRef(id=row.id, name=row.name) for row in rows],
    )


async def list_local_authority_accidents(
    session: AsyncSession,
    local_authority_id: int,
    filters: AccidentListFilters,
) -> tuple[LocalAuthorityContext, list[AccidentListItem], MetaPagination]:
    local_authority = (
        await session.scalars(
            select(LocalAuthority)
            .options(joinedload(LocalAuthority.region))
            .where(LocalAuthority.id == local_authority_id)
        )
    ).first()
    if local_authority is None:
        raise HTTPException(status_code=404, detail="Local authority not found.")

    scoped_filter_data = asdict(filters)
    scoped_filter_data["local_authority_id"] = local_authority_id
    scoped_filters = AccidentListFilters(**scoped_filter_data)
    accidents, total = await list_accidents(session, scoped_filters)
    context = LocalAuthorityContext(
        id=local_authority.id,
        name=local_authority.name,
        region=RegionContext(
            id=local_authority.region.id,
            name=local_authority.region.name,
        ),
    )
    return (
        context,
        accidents,
        MetaPagination(page=filters.page, per_page=filters.per_page, total=total),
    )


def build_scoped_accident_filters(
    page: int,
    per_page: int,
    sort: str,
    order: str,
    date_from: date | None,
    date_to: date | None,
    severity: int | None,
    region_id: int | None,
    road_type_id: int | None,
    weather_condition_id: int | None,
    light_condition_id: int | None,
    speed_limit: int | None,
    urban_or_rural: str | None,
    cluster_id: int | None,
) -> AccidentListFilters:
    return AccidentListFilters(
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

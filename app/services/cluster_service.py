from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accident import Accident
from app.models.cluster import Cluster
from app.models.lookups import LightCondition, LocalAuthority, RoadSurface, WeatherCondition
from app.schemas.accident import AccidentListItem, MetaPagination, NamedRef
from app.schemas.cluster import (
    AnnualTrendPoint,
    ClusterAccidentContext,
    ClusterBBox,
    ClusterDetail,
    ClusterListItem,
    DominantConditions,
)
from app.services.accident_service import AccidentListFilters, list_accidents

ALLOWED_CLUSTER_LABELS = {"Low", "Medium", "High", "Critical"}


def _to_cluster_list_item(
    cluster: Cluster,
    local_authority_id: int | None,
    local_authority_name: str | None,
) -> ClusterListItem:
    return ClusterListItem(
        id=cluster.id,
        centroid_lat=cluster.centroid_lat,
        centroid_lng=cluster.centroid_lng,
        radius_km=cluster.radius_km,
        accident_count=cluster.accident_count,
        fatal_count=cluster.fatal_count,
        serious_count=cluster.serious_count,
        fatal_rate_pct=cluster.fatal_rate_pct,
        severity_label=cluster.severity_label,
        local_authority=(
            NamedRef(id=local_authority_id, name=local_authority_name)
            if local_authority_id is not None and local_authority_name is not None
            else None
        ),
    )


async def _dominant_lookup_label(
    session: AsyncSession,
    cluster_id: int,
    accident_field: Any,
    lookup_model: Any,
) -> str | None:
    row = (
        await session.execute(
            select(lookup_model.label, func.count(Accident.id).label("row_count"))
            .join(lookup_model, accident_field == lookup_model.id)
            .where(Accident.cluster_id == cluster_id, accident_field.is_not(None))
            .group_by(lookup_model.label)
            .order_by(desc("row_count"), lookup_model.label.asc())
            .limit(1)
        )
    ).first()
    return row.label if row is not None else None


async def _dominant_speed_limit(session: AsyncSession, cluster_id: int) -> int | None:
    row = (
        await session.execute(
            select(Accident.speed_limit, func.count(Accident.id).label("row_count"))
            .where(Accident.cluster_id == cluster_id, Accident.speed_limit.is_not(None))
            .group_by(Accident.speed_limit)
            .order_by(desc("row_count"), Accident.speed_limit.asc())
            .limit(1)
        )
    ).first()
    return int(row.speed_limit) if row is not None else None


async def list_clusters(
    session: AsyncSession,
    page: int,
    per_page: int,
    region_id: int | None,
    min_accidents: int,
    severity_label: str | None,
) -> tuple[list[ClusterListItem], MetaPagination]:
    if severity_label is not None and severity_label not in ALLOWED_CLUSTER_LABELS:
        raise HTTPException(
            status_code=400,
            detail="Invalid severity_label. Expected one of: Low, Medium, High, Critical.",
        )

    query = (
        select(Cluster, LocalAuthority.id, LocalAuthority.name)
        .outerjoin(LocalAuthority, LocalAuthority.id == Cluster.local_authority_id)
        .where(Cluster.accident_count >= min_accidents)
    )
    if region_id is not None:
        query = query.where(LocalAuthority.region_id == region_id)
    if severity_label is not None:
        query = query.where(Cluster.severity_label == severity_label)

    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    rows = (
        await session.execute(
            query.order_by(Cluster.accident_count.desc(), Cluster.id.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    data = [
        _to_cluster_list_item(cluster, local_authority_id, local_authority_name)
        for cluster, local_authority_id, local_authority_name in rows
    ]
    meta = MetaPagination(page=page, per_page=per_page, total=total)
    return data, meta


async def get_cluster(session: AsyncSession, cluster_id: int) -> ClusterDetail:
    row = (
        await session.execute(
            select(Cluster, LocalAuthority.id, LocalAuthority.name)
            .outerjoin(LocalAuthority, LocalAuthority.id == Cluster.local_authority_id)
            .where(Cluster.id == cluster_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Cluster not found.")

    cluster, local_authority_id, local_authority_name = row
    list_item = _to_cluster_list_item(cluster, local_authority_id, local_authority_name)

    bbox_row = (
        await session.execute(
            select(
                func.min(Accident.latitude).label("min_lat"),
                func.min(Accident.longitude).label("min_lng"),
                func.max(Accident.latitude).label("max_lat"),
                func.max(Accident.longitude).label("max_lng"),
            ).where(Accident.cluster_id == cluster_id)
        )
    ).first()
    min_lat = bbox_row.min_lat if bbox_row is not None else None
    min_lng = bbox_row.min_lng if bbox_row is not None else None
    max_lat = bbox_row.max_lat if bbox_row is not None else None
    max_lng = bbox_row.max_lng if bbox_row is not None else None
    bbox = ClusterBBox(
        min_lat=float(min_lat) if min_lat is not None else cluster.centroid_lat,
        min_lng=float(min_lng) if min_lng is not None else cluster.centroid_lng,
        max_lat=float(max_lat) if max_lat is not None else cluster.centroid_lat,
        max_lng=float(max_lng) if max_lng is not None else cluster.centroid_lng,
    )

    dominant_conditions = DominantConditions(
        weather=await _dominant_lookup_label(
            session,
            cluster_id,
            Accident.weather_condition_id,
            WeatherCondition,
        ),
        light=await _dominant_lookup_label(
            session,
            cluster_id,
            Accident.light_condition_id,
            LightCondition,
        ),
        road_surface=await _dominant_lookup_label(
            session,
            cluster_id,
            Accident.road_surface_id,
            RoadSurface,
        ),
        speed_limit=await _dominant_speed_limit(session, cluster_id),
    )

    trend_rows = (
        await session.execute(
            select(
                func.extract("year", Accident.date).label("year"),
                func.count(Accident.id).label("accident_count"),
            )
            .where(Accident.cluster_id == cluster_id)
            .group_by("year")
            .order_by("year")
        )
    ).all()
    annual_trend = [
        AnnualTrendPoint(year=int(row.year), accident_count=int(row.accident_count))
        for row in trend_rows
    ]

    return ClusterDetail(
        **list_item.model_dump(),
        bbox=bbox,
        dominant_conditions=dominant_conditions,
        annual_trend=annual_trend,
    )


def build_cluster_scoped_filters(
    page: int,
    per_page: int,
    sort: str,
    order: str,
    date_from: date | None,
    date_to: date | None,
    severity: int | None,
    region_id: int | None,
    local_authority_id: int | None,
    road_type_id: int | None,
    weather_condition_id: int | None,
    light_condition_id: int | None,
    speed_limit: int | None,
    urban_or_rural: str | None,
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
        local_authority_id=local_authority_id,
        road_type_id=road_type_id,
        weather_condition_id=weather_condition_id,
        light_condition_id=light_condition_id,
        speed_limit=speed_limit,
        urban_or_rural=urban_or_rural,
    )


async def list_cluster_accidents(
    session: AsyncSession,
    cluster_id: int,
    filters: AccidentListFilters,
) -> tuple[ClusterAccidentContext, list[AccidentListItem], MetaPagination]:
    cluster = await session.get(Cluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found.")

    scoped_filter_data = asdict(filters)
    scoped_filter_data["cluster_id"] = cluster_id
    scoped_filters = AccidentListFilters(**scoped_filter_data)

    accidents, total = await list_accidents(session, scoped_filters)
    context = ClusterAccidentContext(
        id=cluster.id,
        centroid_lat=cluster.centroid_lat,
        centroid_lng=cluster.centroid_lng,
        severity_label=cluster.severity_label,
    )
    meta = MetaPagination(page=filters.page, per_page=filters.per_page, total=total)
    return context, accidents, meta

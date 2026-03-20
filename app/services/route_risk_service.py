from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import asin, cos, pi, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.route_risk_constants import (
    ACCIDENT_DENSITY_WEIGHT,
    CLUSTER_PROXIMITY_DECAY_KM,
    CLUSTER_PROXIMITY_WEIGHT,
    FACTOR_DESCRIPTIONS,
    RISK_LABEL_RANGES,
    ROUTE_RISK_FORMULA,
    ROUTE_RISK_WEIGHTS,
    SEVERITY_WEIGHT,
    SPEED_LIMIT_WEIGHT,
    TIME_RISK_WEIGHT,
    risk_label_for_score,
)
from app.models.accident import Accident
from app.models.cluster import Cluster
from app.schemas.route_risk import (
    RouteRiskData,
    RouteRiskFactors,
    RouteRiskOptions,
    RouteRiskQuery,
    RouteRiskRequest,
    RouteRiskResponse,
    RouteRiskScoringModelData,
    RouteRiskScoringModelResponse,
    RouteRiskSegment,
    RouteSummary,
)


@dataclass(slots=True)
class _RouteSegment:
    segment_id: int
    start: tuple[float, float]
    end: tuple[float, float]
    midpoint: tuple[float, float]
    length_km: float


@dataclass(slots=True)
class _NearbyAccident:
    severity_id: int
    speed_limit: int | None


@dataclass(slots=True)
class _ClusterRecord:
    cluster_id: int
    centroid_lat: float
    centroid_lng: float
    radius_km: float


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return earth_radius_km * 2 * asin(sqrt(a))


def _clip01(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _default_day_of_week(now: datetime) -> int:
    # API convention is 1=Sunday, 7=Saturday.
    iso_day = now.isoweekday()  # Monday=1 ... Sunday=7
    return 1 if iso_day == 7 else iso_day + 1


def _resolve_time_context(request: RouteRiskRequest) -> tuple[str, int, int]:
    options = request.options
    now = datetime.now(UTC)
    time_of_day = options.time_of_day if options and options.time_of_day else now.strftime("%H:%M")
    day_of_week = (
        options.day_of_week if options and options.day_of_week else _default_day_of_week(now)
    )
    hour = int(time_of_day.split(":", maxsplit=1)[0])
    return time_of_day, day_of_week, hour


def _point_at_distance(
    waypoints: list[tuple[float, float]],
    leg_lengths: list[float],
    target_km: float,
) -> tuple[float, float]:
    if target_km <= 0:
        return waypoints[0]

    traversed = 0.0
    for idx, leg_km in enumerate(leg_lengths):
        start = waypoints[idx]
        end = waypoints[idx + 1]
        if leg_km <= 0:
            continue

        next_distance = traversed + leg_km
        if target_km <= next_distance:
            fraction = (target_km - traversed) / leg_km
            lat = start[0] + fraction * (end[0] - start[0])
            lng = start[1] + fraction * (end[1] - start[1])
            return (lat, lng)
        traversed = next_distance

    return waypoints[-1]


def _decompose_route(
    waypoints: list[tuple[float, float]],
    segment_length_km: float,
) -> tuple[list[_RouteSegment], float]:
    leg_lengths = [
        _haversine_km(start[0], start[1], end[0], end[1])
        for start, end in zip(waypoints, waypoints[1:], strict=False)
    ]
    total_distance_km = sum(leg_lengths)
    if total_distance_km <= 0:
        raise HTTPException(
            status_code=400,
            detail="Route waypoints collapse to zero distance.",
        )

    marks = [0.0]
    next_mark = segment_length_km
    while next_mark < total_distance_km:
        marks.append(next_mark)
        next_mark += segment_length_km
    if marks[-1] != total_distance_km:
        marks.append(total_distance_km)

    segments: list[_RouteSegment] = []
    for index in range(len(marks) - 1):
        start_mark = marks[index]
        end_mark = marks[index + 1]
        midpoint_mark = (start_mark + end_mark) / 2.0

        segments.append(
            _RouteSegment(
                segment_id=index + 1,
                start=_point_at_distance(waypoints, leg_lengths, start_mark),
                end=_point_at_distance(waypoints, leg_lengths, end_mark),
                midpoint=_point_at_distance(waypoints, leg_lengths, midpoint_mark),
                length_km=end_mark - start_mark,
            )
        )

    return segments, total_distance_km


async def _load_clusters(session: AsyncSession) -> list[_ClusterRecord]:
    rows = (
        await session.execute(
            select(Cluster.id, Cluster.centroid_lat, Cluster.centroid_lng, Cluster.radius_km)
        )
    ).all()
    return [
        _ClusterRecord(
            cluster_id=int(row.id),
            centroid_lat=float(row.centroid_lat),
            centroid_lng=float(row.centroid_lng),
            radius_km=float(row.radius_km),
        )
        for row in rows
    ]


async def _fetch_nearby_accidents(
    session: AsyncSession,
    midpoint: tuple[float, float],
    buffer_radius_km: float,
) -> list[_NearbyAccident]:
    lat, lng = midpoint
    delta = buffer_radius_km / 111.0

    rows = (
        await session.execute(
            select(
                Accident.severity_id,
                Accident.speed_limit,
                Accident.latitude,
                Accident.longitude,
            ).where(
                Accident.latitude.is_not(None),
                Accident.longitude.is_not(None),
                Accident.latitude.between(lat - delta, lat + delta),
                Accident.longitude.between(lng - delta, lng + delta),
            )
        )
    ).all()

    nearby: list[_NearbyAccident] = []
    for row in rows:
        row_lat = float(row.latitude)
        row_lng = float(row.longitude)
        if _haversine_km(lat, lng, row_lat, row_lng) <= buffer_radius_km:
            nearby.append(
                _NearbyAccident(
                    severity_id=int(row.severity_id),
                    speed_limit=int(row.speed_limit) if row.speed_limit is not None else None,
                )
            )

    return nearby


def _accident_density_factor(nearby_count: int, buffer_radius_km: float) -> float:
    if nearby_count == 0 or cache.P99_DENSITY <= 0:
        return 0.0

    area_km2 = pi * (buffer_radius_km**2)
    density = nearby_count / area_km2
    return _clip01(density / cache.P99_DENSITY)


def _severity_factor(nearby: list[_NearbyAccident]) -> float:
    if not nearby:
        return 0.0

    fatal = sum(1 for item in nearby if item.severity_id == 1)
    serious = sum(1 for item in nearby if item.severity_id == 2)
    slight = sum(1 for item in nearby if item.severity_id == 3)
    weighted = 3 * fatal + 2 * serious + slight
    return _clip01(weighted / (3 * len(nearby)))


def _time_factor(day_of_week: int, hour: int) -> float:
    if not cache.HEATMAP:
        return 0.0

    max_cell = max(
        (count for by_hour in cache.HEATMAP.values() for count in by_hour.values()),
        default=0,
    )
    if max_cell <= 0:
        return 0.0

    cell = cache.HEATMAP.get(day_of_week, {}).get(hour, 0)
    return _clip01(cell / max_cell)


def _dominant_speed_limit(nearby: list[_NearbyAccident]) -> int | None:
    speed_counts: dict[int, int] = {}
    for item in nearby:
        if item.speed_limit is None:
            continue
        speed_counts[item.speed_limit] = speed_counts.get(item.speed_limit, 0) + 1

    if not speed_counts:
        return None

    max_count = max(speed_counts.values())
    return min(speed for speed, count in speed_counts.items() if count == max_count)


def _speed_limit_factor(dominant_speed_limit: int | None) -> float:
    if dominant_speed_limit is None or not cache.SPEED_FATAL_RATES:
        return 0.0

    max_rate = max(cache.SPEED_FATAL_RATES.values(), default=0.0)
    if max_rate <= 0:
        return 0.0

    rate = cache.SPEED_FATAL_RATES.get(dominant_speed_limit, 0.0)
    return _clip01(rate / max_rate)


def _cluster_factor(
    midpoint: tuple[float, float],
    buffer_radius_km: float,
    clusters: list[_ClusterRecord],
) -> tuple[list[int], float]:
    if not clusters:
        return [], 0.0

    nearby_cluster_ids: list[int] = []
    inside_any_cluster = False
    nearest_edge_distance_km: float | None = None

    for cluster in clusters:
        center_distance_km = _haversine_km(
            midpoint[0],
            midpoint[1],
            cluster.centroid_lat,
            cluster.centroid_lng,
        )
        edge_distance_km = max(center_distance_km - cluster.radius_km, 0.0)

        if nearest_edge_distance_km is None or edge_distance_km < nearest_edge_distance_km:
            nearest_edge_distance_km = edge_distance_km

        if center_distance_km <= cluster.radius_km:
            inside_any_cluster = True

        if center_distance_km <= cluster.radius_km + buffer_radius_km:
            nearby_cluster_ids.append(cluster.cluster_id)

    nearby_cluster_ids = sorted(set(nearby_cluster_ids))

    if inside_any_cluster:
        return nearby_cluster_ids, 1.0

    if nearest_edge_distance_km is None:
        return nearby_cluster_ids, 0.0

    proximity = _clip01(1.0 - (nearest_edge_distance_km / CLUSTER_PROXIMITY_DECAY_KM))
    return nearby_cluster_ids, proximity


async def score_route_risk(
    session: AsyncSession,
    request: RouteRiskRequest,
) -> RouteRiskResponse:
    options = request.options or RouteRiskOptions()

    time_of_day, day_of_week, hour = _resolve_time_context(request)
    segments, total_distance_km = _decompose_route(request.waypoints, options.segment_length_km)
    clusters = await _load_clusters(session)

    scored_segments: list[RouteRiskSegment] = []
    segment_scores: list[float] = []
    intersected_clusters: set[int] = set()

    for segment in segments:
        nearby = await _fetch_nearby_accidents(session, segment.midpoint, options.buffer_radius_km)
        dominant_speed_limit = _dominant_speed_limit(nearby)

        f1 = _accident_density_factor(len(nearby), options.buffer_radius_km)
        f2 = _severity_factor(nearby)
        f3 = _time_factor(day_of_week, hour)
        f4 = _speed_limit_factor(dominant_speed_limit)
        nearby_cluster_ids, f5 = _cluster_factor(
            segment.midpoint, options.buffer_radius_km, clusters
        )

        risk_score = _clip01(
            ACCIDENT_DENSITY_WEIGHT * f1
            + SEVERITY_WEIGHT * f2
            + TIME_RISK_WEIGHT * f3
            + SPEED_LIMIT_WEIGHT * f4
            + CLUSTER_PROXIMITY_WEIGHT * f5
        )
        segment_scores.append(risk_score)
        intersected_clusters.update(nearby_cluster_ids)

        scored_segments.append(
            RouteRiskSegment(
                segment_id=segment.segment_id,
                start=(round(segment.start[0], 6), round(segment.start[1], 6)),
                end=(round(segment.end[0], 6), round(segment.end[1], 6)),
                length_km=round(segment.length_km, 3),
                risk_score=round(risk_score, 4),
                risk_label=risk_label_for_score(risk_score),
                factors=RouteRiskFactors(
                    accident_density=round(f1, 4),
                    severity_score=round(f2, 4),
                    time_risk=round(f3, 4),
                    speed_limit_risk=round(f4, 4),
                    cluster_proximity=round(f5, 4),
                ),
                nearby_accidents=len(nearby),
                nearby_cluster_ids=nearby_cluster_ids,
                dominant_speed_limit=dominant_speed_limit,
            )
        )

    aggregate_score = sum(segment_scores) / len(segment_scores)
    peak_index, peak_score = max(enumerate(segment_scores), key=lambda item: item[1])

    return RouteRiskResponse(
        data=RouteRiskData(
            route_summary=RouteSummary(
                total_distance_km=round(total_distance_km, 3),
                segment_count=len(scored_segments),
                aggregate_risk_score=round(aggregate_score, 4),
                risk_label=risk_label_for_score(aggregate_score),
                peak_segment_risk=round(peak_score, 4),
                peak_segment_id=peak_index + 1,
                clusters_intersected=len(intersected_clusters),
            ),
            segments=scored_segments,
        ),
        query=RouteRiskQuery(
            waypoint_count=len(request.waypoints),
            segment_length_km=options.segment_length_km,
            buffer_radius_km=options.buffer_radius_km,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
        ),
    )


def get_route_risk_scoring_model() -> RouteRiskScoringModelResponse:
    return RouteRiskScoringModelResponse(
        data=RouteRiskScoringModelData(
            formula=ROUTE_RISK_FORMULA,
            weights=ROUTE_RISK_WEIGHTS,
            factor_descriptions=FACTOR_DESCRIPTIONS,
            risk_labels=RISK_LABEL_RANGES,
        )
    )

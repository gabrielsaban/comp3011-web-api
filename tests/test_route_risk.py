from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.route_risk_constants import ROUTE_RISK_WEIGHTS
from app.services import route_risk_service
from tests.fixtures import seed_profile


@pytest.fixture(autouse=True)
def reset_route_risk_caches() -> Generator[None, None, None]:
    cache.reset_startup_caches()
    yield
    cache.reset_startup_caches()


def _set_deterministic_caches() -> None:
    heatmap = {day: {hour: 0 for hour in range(24)} for day in range(1, 8)}
    heatmap[2][8] = 10
    heatmap[5][17] = 4
    cache.HEATMAP.update(heatmap)
    cache.SPEED_FATAL_RATES.update({20: 10.0, 30: 40.0, 40: 80.0, 60: 20.0})
    cache.P99_DENSITY = 1.0


async def test_route_risk_scoring_model_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/analytics/route-risk/scoring-model")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["weights"] == ROUTE_RISK_WEIGHTS
    assert data["risk_labels"]["0.8-1.0"] == "Critical"
    assert "cluster_proximity" in data["factor_descriptions"]


async def test_route_risk_validates_waypoint_shape(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analytics/route-risk",
        json={"waypoints": [[53.8, -1.5]]},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


async def test_route_risk_rejects_zero_length_route(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analytics/route-risk",
        json={"waypoints": [[53.8, -1.5], [53.8, -1.5]]},
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "BAD_REQUEST"


@pytest.mark.parametrize(
    ("options", "invalid_field"),
    [
        ({"segment_length_km": 0.05, "buffer_radius_km": 0.5}, "segment_length_km"),
        ({"segment_length_km": 2.5, "buffer_radius_km": 0.5}, "segment_length_km"),
        ({"segment_length_km": 0.5, "buffer_radius_km": 0.05}, "buffer_radius_km"),
    ],
)
async def test_route_risk_rejects_invalid_option_ranges(
    client: AsyncClient,
    options: dict[str, float],
    invalid_field: str,
) -> None:
    response = await client.post(
        "/api/v1/analytics/route-risk",
        json={"waypoints": [[53.8, -1.5], [53.81, -1.49]], "options": options},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["loc"][-1] == invalid_field for detail in body["error"]["details"])


async def test_route_risk_scores_segment_with_cache_driven_f3_f4_and_cluster_f5(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    _set_deterministic_caches()

    response = await client.post(
        "/api/v1/analytics/route-risk",
        json={
            "waypoints": [[53.7905, -1.5415], [53.7913, -1.5405]],
            "options": {
                "time_of_day": "08:30",
                "day_of_week": 2,
                "segment_length_km": 1.0,
                "buffer_radius_km": 0.6,
            },
        },
    )
    assert response.status_code == 200

    body = response.json()
    summary = body["data"]["route_summary"]
    assert summary["segment_count"] == 1
    assert 0.0 <= summary["aggregate_risk_score"] <= 1.0

    segment = body["data"]["segments"][0]
    assert segment["factors"]["time_risk"] == 1.0
    assert segment["factors"]["speed_limit_risk"] == 1.0
    assert segment["factors"]["cluster_proximity"] == 1.0
    assert 15 in segment["nearby_cluster_ids"]
    assert segment["dominant_speed_limit"] == 40

    query = body["query"]
    assert query["time_of_day"] == "08:30"
    assert query["day_of_week"] == 2

    factors = segment["factors"]
    expected_score = (
        ROUTE_RISK_WEIGHTS["accident_density"] * factors["accident_density"]
        + ROUTE_RISK_WEIGHTS["severity_score"] * factors["severity_score"]
        + ROUTE_RISK_WEIGHTS["time_risk"] * factors["time_risk"]
        + ROUTE_RISK_WEIGHTS["speed_limit_risk"] * factors["speed_limit_risk"]
        + ROUTE_RISK_WEIGHTS["cluster_proximity"] * factors["cluster_proximity"]
    )
    assert segment["risk_score"] == pytest.approx(expected_score, abs=0.02)


async def test_route_risk_cluster_proximity_decays_to_zero_when_far_away(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    _set_deterministic_caches()

    response = await client.post(
        "/api/v1/analytics/route-risk",
        json={
            "waypoints": [[55.2, -3.9], [55.21, -3.91]],
            "options": {
                "time_of_day": "08:30",
                "day_of_week": 2,
                "segment_length_km": 1.0,
                "buffer_radius_km": 0.5,
            },
        },
    )
    assert response.status_code == 200

    segment = response.json()["data"]["segments"][0]
    assert segment["nearby_cluster_ids"] == []
    assert segment["factors"]["cluster_proximity"] == 0.0
    assert segment["nearby_accidents"] == 0
    assert segment["dominant_speed_limit"] is None


async def test_route_risk_defaults_day_and_time_when_options_omitted(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    _set_deterministic_caches()

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object | None = None) -> FixedDateTime:
            return cls(2024, 3, 4, 17, 45, tzinfo=UTC)  # Monday

    monkeypatch.setattr(route_risk_service, "datetime", FixedDateTime)

    response = await client.post(
        "/api/v1/analytics/route-risk",
        json={"waypoints": [[53.8008, -1.5491], [53.8108, -1.5391]]},
    )
    assert response.status_code == 200

    query = response.json()["query"]
    assert query["time_of_day"] == "17:45"
    assert query["day_of_week"] == 2  # Monday -> 2 in API convention (1=Sunday)

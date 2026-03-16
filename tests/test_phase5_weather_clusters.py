from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures import seed_profile


async def test_get_weather_stations_returns_linked_station_collection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/weather-stations")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"page": 1, "per_page": 25, "total": 1}
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == 3802
    assert body["data"][0]["linked_accident_count"] == 3


async def test_get_weather_stations_active_on_filter_can_return_empty(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/weather-stations",
        params={"active_on": "2018-01-01"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["total"] == 0


async def test_get_weather_station_by_id_returns_observation_summary(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/weather-stations/3802")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == 3802
    summary = data["observation_summary"]
    assert abs(summary["mean_temperature_c"] - 7.25) < 0.001
    assert abs(summary["mean_visibility_m"] - 6400.0) < 0.001
    assert summary["observations_with_precipitation"] == 1


async def test_get_weather_station_by_id_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/weather-stations/999")
    assert response.status_code == 404


async def test_get_clusters_returns_default_filtered_list(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/clusters")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"page": 1, "per_page": 25, "total": 2}
    assert [row["id"] for row in body["data"]] == [14, 15]


async def test_get_clusters_supports_filter_combinations(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    high_min = await client.get("/api/v1/clusters", params={"min_accidents": 20})
    assert high_min.status_code == 200
    assert [row["id"] for row in high_min.json()["data"]] == [14]

    low_only = await client.get("/api/v1/clusters", params={"severity_label": "Low"})
    assert low_only.status_code == 200
    assert [row["id"] for row in low_only.json()["data"]] == [15]

    region_scoped = await client.get("/api/v1/clusters", params={"region_id": 1})
    assert region_scoped.status_code == 200
    assert region_scoped.json()["meta"]["total"] == 2


async def test_get_clusters_invalid_severity_label_returns_400(client: AsyncClient) -> None:
    response = await client.get("/api/v1/clusters", params={"severity_label": "Extreme"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


async def test_get_cluster_by_id_returns_detail_with_dominant_conditions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/clusters/14")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == 14
    assert data["local_authority"] == {"id": 14, "name": "Leeds"}
    assert data["bbox"] == {
        "min_lat": 53.8008,
        "min_lng": -1.5491,
        "max_lat": 53.8008,
        "max_lng": -1.5491,
    }
    assert data["dominant_conditions"] == {
        "weather": "Raining no high winds",
        "light": "Daylight",
        "road_surface": "Wet or damp",
        "speed_limit": 30,
    }
    assert data["annual_trend"] == [{"year": 2022, "accident_count": 1}]


async def test_get_cluster_by_id_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/clusters/999")
    assert response.status_code == 404


async def test_get_cluster_accidents_returns_scoped_envelope(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/clusters/15/accidents",
        params={"severity": 1, "sort": "date", "order": "asc"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["context"] == {
        "id": 15,
        "centroid_lat": 53.7909,
        "centroid_lng": -1.541,
        "severity_label": "Low",
    }
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == "2022010012346"


async def test_get_cluster_accidents_can_return_empty_data(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/clusters/15/accidents",
        params={"severity": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["context"]["id"] == 15
    assert body["data"] == []
    assert body["meta"]["total"] == 0


async def test_get_cluster_accidents_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/clusters/999/accidents")
    assert response.status_code == 404

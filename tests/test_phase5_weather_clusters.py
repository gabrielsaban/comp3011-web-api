from datetime import date

from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather import WeatherStation
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


async def test_get_weather_stations_region_filter_applies_scope(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    in_region = await client.get("/api/v1/weather-stations", params={"region_id": 1})
    assert in_region.status_code == 200
    assert in_region.json()["meta"]["total"] == 1

    out_of_region = await client.get("/api/v1/weather-stations", params={"region_id": 999})
    assert out_of_region.status_code == 200
    assert out_of_region.json()["data"] == []
    assert out_of_region.json()["meta"]["total"] == 0


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


async def test_get_weather_station_by_id_unlinked_station_returns_zero_summary(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    await db_session.execute(
        insert(WeatherStation),
        [
            {
                "id": 9001,
                "name": "Unlinked Test Station",
                "latitude": 52.0,
                "longitude": -1.0,
                "elevation_m": 100,
                "active_from": date(2020, 1, 1),
                "active_to": None,
            }
        ],
    )
    await db_session.flush()

    response = await client.get("/api/v1/weather-stations/9001")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["linked_accident_count"] == 0
    assert data["observation_summary"] == {
        "mean_temperature_c": None,
        "mean_precipitation_mm": None,
        "mean_wind_speed_ms": None,
        "mean_visibility_m": None,
        "observations_with_precipitation": 0,
    }


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


async def test_cluster_endpoints_exclude_noise_point_accidents(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    cluster_14 = await client.get("/api/v1/clusters/14/accidents")
    assert cluster_14.status_code == 200
    ids_14 = {row["id"] for row in cluster_14.json()["data"]}
    assert "2022010012348" not in ids_14
    assert "2022010012349" not in ids_14

    cluster_15 = await client.get("/api/v1/clusters/15/accidents")
    assert cluster_15.status_code == 200
    ids_15 = {row["id"] for row in cluster_15.json()["data"]}
    assert "2022010012348" not in ids_15
    assert "2022010012349" not in ids_15


async def test_null_weather_links_do_not_inflate_station_link_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/weather-stations")
    assert response.status_code == 200
    assert response.json()["data"][0]["linked_accident_count"] == 3


async def test_get_cluster_accidents_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/clusters/999/accidents")
    assert response.status_code == 404

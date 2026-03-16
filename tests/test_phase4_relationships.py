from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures import seed_profile


async def test_reference_conditions_returns_all_lookup_tables(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/reference/conditions")
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data.keys()) == {
        "severities",
        "weather_conditions",
        "light_conditions",
        "road_surfaces",
        "road_types",
        "junction_details",
        "vehicle_types",
    }
    assert len(data["severities"]) == 3


async def test_reference_conditions_type_scopes_to_single_table(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/reference/conditions", params={"type": "weather"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data.keys()) == {"weather_conditions"}


async def test_reference_conditions_invalid_type_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/reference/conditions", params={"type": "severity"})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "BAD_REQUEST"


async def test_get_regions_returns_local_authority_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/regions")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0] == {
        "id": 1,
        "name": "Yorkshire and The Humber",
        "local_authority_count": 1,
    }


async def test_get_region_by_id_returns_single_region(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/regions/1")
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Yorkshire and The Humber"


async def test_get_region_by_id_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/regions/999")
    assert response.status_code == 404


async def test_get_region_local_authorities_returns_scoped_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/regions/1/local-authorities")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"context", "data"}
    assert body["context"] == {"id": 1, "name": "Yorkshire and The Humber"}
    assert body["data"] == [{"id": 14, "name": "Leeds"}]


async def test_get_region_local_authorities_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/regions/999/local-authorities")
    assert response.status_code == 404


async def test_get_local_authority_accidents_returns_scoped_collection_with_meta(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/local-authorities/14/accidents",
        params={
            "severity": 1,
            "page": 1,
            "per_page": 1,
            "sort": "date",
            "order": "asc",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"context", "data", "meta"}
    assert body["context"] == {
        "id": 14,
        "name": "Leeds",
        "region": {"id": 1, "name": "Yorkshire and The Humber"},
    }
    assert body["meta"] == {"page": 1, "per_page": 1, "total": 2}
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == "2022010012346"


async def test_get_local_authority_accidents_can_return_empty_data_with_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/local-authorities/14/accidents",
        params={"region_id": 999},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["context"]["id"] == 14
    assert body["data"] == []
    assert body["meta"]["total"] == 0


async def test_get_local_authority_accidents_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/local-authorities/999/accidents")
    assert response.status_code == 404

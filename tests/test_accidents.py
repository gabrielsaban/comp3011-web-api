from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from tests.fixtures import seed_profile


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_get_accidents_list_returns_collection_envelope(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["page"] == 1
    assert body["meta"]["per_page"] == 25
    assert body["meta"]["total"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == "2022010012345"


async def test_get_accident_detail_returns_nested_children(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["vehicles"]) == 1
    assert len(data["casualties"]) == 1
    assert data["weather_observation"]["station_id"] == 3802


async def test_get_accidents_region_filter_can_return_empty(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents", params={"region_id": 999})
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


async def test_post_accident_requires_editor_token(client: AsyncClient) -> None:
    payload = {
        "date": "2024-11-01",
        "time": "17:15:00",
        "day_of_week": 5,
        "latitude": 51.5074,
        "longitude": -0.1278,
        "severity_id": 3,
        "local_authority_id": 14,
        "urban_or_rural": "Urban",
    }
    response = await client.post("/api/v1/accidents", json=payload)
    assert response.status_code == 401


async def test_post_accident_with_editor_creates_record(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    payload = {
        "date": "2024-11-01",
        "time": "17:15:00",
        "day_of_week": 5,
        "latitude": 51.5074,
        "longitude": -0.1278,
        "severity_id": 3,
        "local_authority_id": 14,
        "urban_or_rural": "Urban",
        "police_attended": False,
    }
    response = await client.post("/api/v1/accidents", json=payload, headers=_bearer(token))
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["number_of_vehicles"] == 0
    assert data["number_of_casualties"] == 0


async def test_patch_accident_rejects_count_fields(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345",
        json={"number_of_vehicles": 10},
        headers=_bearer(token),
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(err["loc"][-1] == "number_of_vehicles" for err in error["details"])


async def test_get_accident_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/accidents/nonexistent")
    assert response.status_code == 404


async def test_patch_accident_not_found_returns_404(
    client: AsyncClient,
) -> None:
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/nonexistent",
        json={"severity_id": 1},
        headers=_bearer(token),
    )
    assert response.status_code == 404


async def test_post_accident_invalid_fk_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    payload = {
        "date": "2024-11-01",
        "time": "17:15:00",
        "day_of_week": 5,
        "latitude": 51.5074,
        "longitude": -0.1278,
        "severity_id": 999,
        "local_authority_id": 14,
        "urban_or_rural": "Urban",
    }
    response = await client.post("/api/v1/accidents", json=payload, headers=_bearer(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_delete_accident_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    editor = create_access_token(subject="editor-user", role="editor")
    response = await client.delete(
        "/api/v1/accidents/2022010012345",
        headers=_bearer(editor),
    )
    assert response.status_code == 403


async def test_delete_accident_with_admin_returns_204(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    admin = create_access_token(subject="admin-user", role="admin")
    delete_response = await client.delete(
        "/api/v1/accidents/2022010012345",
        headers=_bearer(admin),
    )
    assert delete_response.status_code == 204

    fetch_response = await client.get("/api/v1/accidents/2022010012345")
    assert fetch_response.status_code == 404

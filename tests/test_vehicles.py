from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from tests.fixtures import seed_profile


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_get_vehicles_returns_ordered_collection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345/vehicles")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["vehicle_ref"] == 1
    assert body["data"][0]["vehicle_type"]["id"] == 9


async def test_get_vehicles_unknown_accident_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/accidents/does-not-exist/vehicles")
    assert response.status_code == 404


async def test_get_vehicle_by_ref_returns_single_item(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345/vehicles/1")
    assert response.status_code == 200
    assert response.json()["data"]["vehicle_ref"] == 1


async def test_get_vehicle_by_ref_not_found_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345/vehicles/99")
    assert response.status_code == 404


async def test_post_vehicle_requires_editor_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.post(
        "/api/v1/accidents/2022010012345/vehicles",
        json={"vehicle_type_id": 9},
    )
    assert response.status_code == 401


async def test_post_vehicle_assigns_next_ref_and_updates_accident_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    create_response = await client.post(
        "/api/v1/accidents/2022010012345/vehicles",
        json={
            "vehicle_type_id": 11,
            "age_of_driver": 41,
            "sex_of_driver": "Female",
            "journey_purpose": "Other",
        },
        headers=_bearer(token),
    )
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["vehicle_ref"] == 2
    assert created["vehicle_type"]["id"] == 11

    accident_response = await client.get("/api/v1/accidents/2022010012345")
    assert accident_response.status_code == 200
    assert accident_response.json()["data"]["number_of_vehicles"] == 2


async def test_post_vehicle_invalid_fk_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.post(
        "/api/v1/accidents/2022010012345/vehicles",
        json={"vehicle_type_id": 999},
        headers=_bearer(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_post_vehicle_unknown_accident_returns_404(client: AsyncClient) -> None:
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.post(
        "/api/v1/accidents/does-not-exist/vehicles",
        json={"vehicle_type_id": 9},
        headers=_bearer(token),
    )
    assert response.status_code == 404


async def test_patch_vehicle_requires_editor_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/vehicles/1",
        json={"age_of_driver": 35},
    )
    assert response.status_code == 401


async def test_patch_vehicle_updates_fields(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/vehicles/1",
        json={"engine_capacity_cc": 1800, "propulsion_code": "Hybrid"},
        headers=_bearer(token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["engine_capacity_cc"] == 1800
    assert data["propulsion_code"] == "Hybrid"


async def test_patch_vehicle_not_found_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/vehicles/77",
        json={"age_of_driver": 50},
        headers=_bearer(token),
    )
    assert response.status_code == 404


async def test_delete_vehicle_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.delete(
        "/api/v1/accidents/2022010012345/vehicles/1",
        headers=_bearer(token),
    )
    assert response.status_code == 403


async def test_delete_vehicle_nulls_casualty_link_and_decrements_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    admin = create_access_token(subject="admin-user", role="admin")
    delete_response = await client.delete(
        "/api/v1/accidents/2022010012345/vehicles/1",
        headers=_bearer(admin),
    )
    assert delete_response.status_code == 204

    accident_response = await client.get("/api/v1/accidents/2022010012345")
    assert accident_response.status_code == 200
    accident = accident_response.json()["data"]
    assert accident["number_of_vehicles"] == 0
    assert accident["vehicles"] == []
    assert accident["casualties"][0]["vehicle_ref"] is None


async def test_vehicle_count_roundtrip_create_then_delete_restores_baseline(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    editor = create_access_token(subject="editor-user", role="editor")
    admin = create_access_token(subject="admin-user", role="admin")

    create_response = await client.post(
        "/api/v1/accidents/2022010012345/vehicles",
        json={"vehicle_type_id": 11},
        headers=_bearer(editor),
    )
    assert create_response.status_code == 201
    new_ref = create_response.json()["data"]["vehicle_ref"]

    after_create = await client.get("/api/v1/accidents/2022010012345")
    assert after_create.status_code == 200
    assert after_create.json()["data"]["number_of_vehicles"] == 2

    delete_response = await client.delete(
        f"/api/v1/accidents/2022010012345/vehicles/{new_ref}",
        headers=_bearer(admin),
    )
    assert delete_response.status_code == 204

    after_delete = await client.get("/api/v1/accidents/2022010012345")
    assert after_delete.status_code == 200
    assert after_delete.json()["data"]["number_of_vehicles"] == 1


async def test_delete_vehicle_not_found_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    admin = create_access_token(subject="admin-user", role="admin")
    response = await client.delete(
        "/api/v1/accidents/2022010012345/vehicles/99",
        headers=_bearer(admin),
    )
    assert response.status_code == 404

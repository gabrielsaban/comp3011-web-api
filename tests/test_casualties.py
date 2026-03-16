from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from tests.fixtures import seed_profile


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_get_casualties_returns_ordered_collection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345/casualties")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["casualty_ref"] == 1
    assert body["data"][0]["severity"]["id"] == 2


async def test_get_casualties_unknown_accident_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/accidents/does-not-exist/casualties")
    assert response.status_code == 404


async def test_get_casualty_by_ref_returns_single_item(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345/casualties/1")
    assert response.status_code == 200
    assert response.json()["data"]["casualty_ref"] == 1


async def test_get_casualty_by_ref_not_found_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.get("/api/v1/accidents/2022010012345/casualties/99")
    assert response.status_code == 404


async def test_post_casualty_requires_editor_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.post(
        "/api/v1/accidents/2022010012345/casualties",
        json={"severity_id": 3, "age": 29},
    )
    assert response.status_code == 401


async def test_post_casualty_unknown_accident_returns_404(client: AsyncClient) -> None:
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.post(
        "/api/v1/accidents/does-not-exist/casualties",
        json={"severity_id": 3, "age": 29},
        headers=_bearer(token),
    )
    assert response.status_code == 404


async def test_post_casualty_invalid_vehicle_ref_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.post(
        "/api/v1/accidents/2022010012345/casualties",
        json={"severity_id": 3, "vehicle_ref": 99, "age": 29},
        headers=_bearer(token),
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert any(error["loc"][-1] == "vehicle_ref" for error in body["details"])


async def test_post_casualty_assigns_next_ref_updates_count_and_derives_age_band(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    create_response = await client.post(
        "/api/v1/accidents/2022010012345/casualties",
        json={
            "severity_id": 3,
            "vehicle_ref": 1,
            "casualty_class": "Passenger",
            "casualty_type": "Car occupant",
            "sex": "Female",
            "age": 29,
        },
        headers=_bearer(token),
    )
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["casualty_ref"] == 2
    assert created["age_band"] == "26-35"

    accident_response = await client.get("/api/v1/accidents/2022010012345")
    assert accident_response.status_code == 200
    assert accident_response.json()["data"]["number_of_casualties"] == 2


async def test_post_casualty_with_null_age_yields_null_age_band(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.post(
        "/api/v1/accidents/2022010012345/casualties",
        json={"severity_id": 3, "vehicle_ref": 1, "age": None},
        headers=_bearer(token),
    )
    assert response.status_code == 201
    assert response.json()["data"]["age_band"] is None


async def test_patch_casualty_requires_editor_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/casualties/1",
        json={"age": 40},
    )
    assert response.status_code == 401


async def test_patch_casualty_updates_age_and_recomputes_age_band(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/casualties/1",
        json={"age": 40, "sex": "Female"},
        headers=_bearer(token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["age"] == 40
    assert data["age_band"] == "36-45"
    assert data["sex"] == "Female"


async def test_patch_casualty_can_clear_age_and_age_band(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/casualties/1",
        json={"age": None},
        headers=_bearer(token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["age"] is None
    assert data["age_band"] is None


async def test_patch_casualty_invalid_vehicle_ref_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/casualties/1",
        json={"vehicle_ref": 42},
        headers=_bearer(token),
    )
    assert response.status_code == 422


async def test_patch_casualty_not_found_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.patch(
        "/api/v1/accidents/2022010012345/casualties/77",
        json={"age": 50},
        headers=_bearer(token),
    )
    assert response.status_code == 404


async def test_delete_casualty_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    token = create_access_token(subject="editor-user", role="editor")
    response = await client.delete(
        "/api/v1/accidents/2022010012345/casualties/1",
        headers=_bearer(token),
    )
    assert response.status_code == 403


async def test_delete_casualty_decrements_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    admin = create_access_token(subject="admin-user", role="admin")
    delete_response = await client.delete(
        "/api/v1/accidents/2022010012345/casualties/1",
        headers=_bearer(admin),
    )
    assert delete_response.status_code == 204

    accident_response = await client.get("/api/v1/accidents/2022010012345")
    assert accident_response.status_code == 200
    accident = accident_response.json()["data"]
    assert accident["number_of_casualties"] == 0
    assert accident["casualties"] == []


async def test_delete_casualty_not_found_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "minimal_crud")
    admin = create_access_token(subject="admin-user", role="admin")
    response = await client.delete(
        "/api/v1/accidents/2022010012345/casualties/99",
        headers=_bearer(admin),
    )
    assert response.status_code == 404

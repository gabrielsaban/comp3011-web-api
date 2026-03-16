import pytest
from httpx import AsyncClient

from app.core.auth import create_access_token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path", ["/_auth/editor-check", "/_auth/admin-check"])
async def test_missing_bearer_token_returns_401(client: AsyncClient, path: str) -> None:
    response = await client.post(path)
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Missing bearer token.",
            "details": [],
        }
    }


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post("/_auth/editor-check", headers=_bearer("invalid-token"))
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Invalid authentication token.",
            "details": [],
        }
    }


async def test_expired_token_returns_401(client: AsyncClient) -> None:
    expired = create_access_token(subject="expired-user", role="editor", expires_minutes=-1)
    response = await client.post("/_auth/editor-check", headers=_bearer(expired))
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Token has expired.",
            "details": [],
        }
    }


async def test_editor_token_can_access_editor_route(client: AsyncClient) -> None:
    editor_token = create_access_token(subject="editor-user", role="editor")
    response = await client.post("/_auth/editor-check", headers=_bearer(editor_token))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "role": "editor"}


async def test_editor_token_cannot_access_admin_route(client: AsyncClient) -> None:
    editor_token = create_access_token(subject="editor-user", role="editor")
    response = await client.post("/_auth/admin-check", headers=_bearer(editor_token))
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "FORBIDDEN",
            "message": "Admin role required.",
            "details": [],
        }
    }


async def test_admin_token_can_access_admin_route(client: AsyncClient) -> None:
    admin_token = create_access_token(subject="admin-user", role="admin")
    response = await client.post("/_auth/admin-check", headers=_bearer(admin_token))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "role": "admin"}

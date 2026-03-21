from __future__ import annotations

import json

from httpx import AsyncClient
from starlette.requests import Request

from app.core.auth import create_access_token
from app.main import internal_error_handler


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_error_envelope(
    body: dict[str, object],
    *,
    code: str,
) -> None:
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error.keys()) == {"code", "message", "details"}
    assert error["code"] == code


async def test_400_bad_request_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/reference/conditions", params={"type": "unknown"})
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body, code="BAD_REQUEST")


async def test_401_unauthorized_error_envelope_and_bearer_header(client: AsyncClient) -> None:
    response = await client.post("/_auth/editor-check")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    body = response.json()
    _assert_error_envelope(body, code="UNAUTHORIZED")


async def test_403_forbidden_error_envelope(client: AsyncClient) -> None:
    editor_token = create_access_token(subject="editor-user", role="editor")
    response = await client.post("/_auth/admin-check", headers=_bearer(editor_token))
    assert response.status_code == 403
    body = response.json()
    _assert_error_envelope(body, code="FORBIDDEN")


async def test_404_not_found_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/accidents/NOT_A_REAL_ID")
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body, code="NOT_FOUND")


async def test_422_validation_error_envelope(client: AsyncClient) -> None:
    response = await client.post("/api/v1/analytics/route-risk", json={"waypoints": [[53.8, -1.5]]})
    assert response.status_code == 422
    body = response.json()
    _assert_error_envelope(body, code="VALIDATION_ERROR")


async def test_500_internal_error_envelope_shape() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
        }
    )
    response = await internal_error_handler(request, Exception("boom"))
    assert response.status_code == 500
    body = json.loads(response.body)
    _assert_error_envelope(body, code="INTERNAL_ERROR")

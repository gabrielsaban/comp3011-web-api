# Error Code Catalog

Canonical error envelope across the API:

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "Human-readable summary.",
    "details": []
  }
}
```

All error responses use `details` (empty list when no structured detail is available).

## Codes

| HTTP status | Code | Trigger source | Typical trigger |
|---|---|---|---|
| 400 | `BAD_REQUEST` | `app/main.py` 400 handler | Domain validation failures raised as `HTTPException(status_code=400)` (for example invalid reference `type`). |
| 401 | `UNAUTHORIZED` | `app/core/auth.py`, `app/dependencies.py` via `AuthError` | Missing bearer token, invalid/expired token, malformed token claims. |
| 403 | `FORBIDDEN` | `app/dependencies.py` via `AuthError` | Authenticated user lacks required role (`editor`/`admin`). |
| 404 | `NOT_FOUND` | `app/main.py` 404 handler | Unknown resource IDs or missing parent resources. |
| 422 | `VALIDATION_ERROR` | FastAPI request validation handler in `app/main.py` | Request payload/query/path shape/value validation failures. |
| 500 | `INTERNAL_ERROR` | `app/main.py` 500 handler | Unhandled server exceptions. |

## Notes

- `401` responses include `WWW-Authenticate: Bearer`.
- For `422`, `details` contains field-level items with `loc`, `msg`, and `type`.
- Messages are intentionally concise and non-sensitive.

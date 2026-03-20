# OpenAPI Reconciliation and Export

FastAPI-generated OpenAPI is the source of truth for implemented behavior.

## Export Command

Generate a snapshot without starting the server:

```bash
uv run python scripts/export_openapi.py --output docs/openapi.snapshot.json
```

## Reconciliation Checklist

When reconciling with `docs/api-spec.md`, verify:

- route path and method coverage
- request body fields and validation rules
- response envelope shapes (`error` and success models)
- status codes (`200/201/204/400/401/403/404/422/500` as applicable)
- auth requirements on write/protected endpoints

## Working Rule

- If implementation differs from `docs/api-spec.md`, update either:
  - code/tests (when spec is correct), or
  - docs (when implementation is intentionally finalized and defended).
- Keep PR notes explicit about intentional deviations.

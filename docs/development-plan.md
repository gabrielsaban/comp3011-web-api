# Development Plan

## Purpose

This document defines the implementation sequence and working practices for building the UK Road Traffic Accidents API in a defensible, test-first, security-aware way.

It is intended to keep delivery consistent with:

- `docs/project-brief.md`
- `docs/api-spec.md`
- `docs/architecture.md`

## Delivery Principles

- Build thin routers and move logic into services.
- Keep every migration reversible and traceable.
- Treat tests as deliverables, not cleanup.
- Add auth/security controls before broad endpoint expansion.
- Keep docs synchronized with implementation at each milestone.
- Prefer simple, explainable implementations over speculative optimizations.

## Git and Branching Strategy

For a solo coursework project, use short-lived feature branches with a protected `main`.

- `main`: always runnable, tested baseline.
- `feat/<area>`: new endpoint groups or major features.
- `fix/<area>`: bug fixes.
- `docs/<area>`: documentation-only changes.
- `chore/<area>`: tooling, CI, dependency housekeeping.

Commit style:

- `feat(api): add accidents list endpoint`
- `fix(auth): enforce admin role on delete`
- `test(analytics): add weather correlation edge cases`
- `docs(architecture): clarify cache invalidation`
- `chore(ci): add pytest workflow`

Rules:

- Keep commits small and single-purpose.
- Rebase feature branches onto latest `main` before merge.
- Merge only when tests pass locally.
- Do not mix schema, endpoint logic, and unrelated docs in one commit.
- Use pull requests even for solo work to preserve review notes and rationale.

Branch granularity guidance:

- Use one branch per endpoint slice or behavior change, not one branch per phase.
- Example for Phase 3: separate branches for accident CRUD, vehicle CRUD, casualty CRUD, and count-field protections.

## Implementation Sequence

### Phase 0: Project Bootstrap

Deliverables:

- Dependency manifest (`pyproject.toml` or `requirements.txt`) committed.
- `docker-compose.yml` with local PostgreSQL service.
- `.env.example` with required settings (`DATABASE_URL`, JWT settings, import paths).
- Linting/type-checking tooling (`ruff`, `mypy`) configured and runnable.
- Test quality tooling (`pytest-cov`) configured for coverage reporting.
- FastAPI app skeleton, configuration, dependency injection.
- SQLAlchemy async setup and session management.
- Alembic setup.
- OpenAPI baseline exposed at `/docs` and `/openapi.json`.
- Basic pytest setup with async support.
- CI workflow (`.github/workflows/ci.yml`) running lint, type-check, and tests with PostgreSQL service container.

Exit criteria:

- Fresh clone can run app locally using documented steps.
- Health/basic route test passes.
- `alembic upgrade head` works against local Docker PostgreSQL.
- `.env.example` is sufficient to bootstrap a local `.env`.
- `ruff`, `mypy`, tests, and coverage reporting run in CI on each push/PR.

### Phase 1: Core Schema and Migrations

Deliverables:

- Tables and indexes from `docs/architecture.md`.
- Migration creation order explicitly enforced:
  - lookup tables -> `weather_station` -> `weather_observation` -> `cluster` -> `accident` -> `vehicle` -> `casualty`
- FK constraints declared in the initial table definitions where ordering allows; avoid unnecessary post-creation `ALTER TABLE` steps.
- Composite integrity for casualty-to-vehicle linkage.
- Deterministic fixture seed module with explicit profiles:
  - `minimal_crud`: minimal relational set for CRUD and auth tests
  - `analytics_route_risk`: weather-linked rows, NULL weather rows, cluster noise points, known severity/time/speed distributions

Exit criteria:

- Migration applies cleanly on empty DB.
- Migration downgrade/upgrade cycle passes.
- Schema smoke tests pass.
- Fixture seed can populate a deterministic test baseline from scratch.

### Phase 2: Auth and Security Baseline

Deliverables:

- JWT validation dependency.
- Role checks (`editor`, `admin`) for write routes.
- Standard error envelope for `401` and `403`.
- Token issuance strategy for local/demo/testing:
  - signed tokens via shared secret in config
  - helper utility (`scripts/mint_token.py`) for non-interactive token generation

Exit criteria:

- Unauthorized and forbidden integration tests pass.
- Write endpoints are protected; GET endpoints remain public.
- Token helper can mint valid `editor` and `admin` tokens for manual API testing.

### Phase 3: CRUD Foundation (Accident, Vehicle, Casualty)

Deliverables:

- Full CRUD endpoints per spec.
- Correct count maintenance for `number_of_vehicles` and `number_of_casualties`.
- Concurrency-safe ordinal assignment for child resources:
  - `POST /accidents/:id/vehicles` assigns next `vehicle_ref` without race conditions
  - `POST /accidents/:id/casualties` assigns next `casualty_ref` without race conditions
  - implement with transaction-safe strategy (for example, parent-row locking or equivalent)
- Vehicle delete behavior that nulls linked casualty `vehicle_ref` first.
- `PATCH /accidents/:id` rejects count fields with `422`.
- `GET /accidents` filter implementation and tests:
  - all documented filters, pagination, and sorting
  - combined-filter behavior and empty-result handling
  - `region_id` two-hop join path (`accident -> local_authority -> region`)

Exit criteria:

- Integration tests for all CRUD status paths.
- Integration tests for `GET /accidents` filter combinations and pagination metadata.
- Query-level validation that `region_id` join filter is correct and remains within performance targets.
- Service-layer query logic only (checked by code review, not automated test).

### Phase 4: Lookup and Relationship Endpoints

Deliverables:

- `GET /reference/conditions` as intentionally non-standard REST aggregate response.
- Region and local-authority relationship endpoints.
- Scoped collection envelope behavior.

Exit criteria:

- Response shape tests pass for context/meta envelopes.
- Query parameter validation tests pass.
- `GET /reference/conditions` behavior remains aligned with `docs/api-spec.md` design note.

### Phase 5: Weather and Cluster Resources

Deliverables:

- Weather station endpoints.
- Cluster endpoints and scoped accidents-by-cluster.

Implementation notes:

- `GET /clusters` `local_authority` field is resolved from `cluster.local_authority_id`, which is stored during import (not computed at read time).
- `GET /clusters/:id` `dominant_conditions` requires four read-time subqueries (dominant weather, light, road surface, speed limit among cluster members). Decide at implementation whether to compute at read time (acceptable given bounded cluster membership) or pre-compute and store as a JSONB column during import. Document the choice.

Exit criteria:

- Coverage tests for nullable weather links and cluster noise points.
- Pagination and filtering behavior validated.

### Phase 6: Analytics Endpoints (Excluding Route Risk)

Deliverables:

- Analytical endpoints excluding route risk.
- Zero-fill for accidents-by-time heatmap.
- Min-count protections for fatal-condition-combinations.
- MIDAS dimension support with `coverage_pct` handling.
- `GET /analytics/weather-correlation` with metric banding and coverage reporting.

Exit criteria:

- Deterministic query tests using fixed fixture data.
- Edge-case tests for empty/partial weather coverage.

### Phase 7: Import Pipeline and Startup Caches

Deliverables:

- STATS19 import.
- MIDAS reload and matching aligned to full-refresh import semantics.
- DBSCAN cluster generation and backfill.
- Startup cache preload (`HEATMAP`, `SPEED_FATAL_RATES`, `P99_DENSITY`) from current DB state.
- Import policy for API-created records is explicit:
  - imported dataset is authoritative
  - API-created accident records are ephemeral between full imports and may be removed by refresh
- Explicit re-run semantics:
  - STATS19 + MIDAS import uses full refresh semantics (truncate target tables and reload from source).
  - corrected source rows are reflected on re-import; removed source rows are removed from DB state on re-import.
  - Cluster recomputation is full replacement, not incremental upsert.
  - FK-safe teardown/rebuild sequence is explicit:
    - set `accident.weather_observation_id = NULL` and `accident.cluster_id = NULL`
    - truncate/reload STATS19 accident/vehicle/casualty tables
    - reload MIDAS station/observation tables for the import window
    - re-run MIDAS matching and assign `weather_observation_id`
    - truncate/rebuild `cluster` table
    - reassign `cluster_id`
    - rebuild startup caches

Cache policy:

- Caches are loaded on startup from persisted dataset state.
- No runtime mutation-driven cache invalidation hooks are implemented.
- Cache refresh occurs on process restart (including after full dataset re-import).

Exit criteria:

- Import runs end-to-end on sample dataset.
- Re-run behavior is deterministic and documented:
  - aggregate results and assignments are deterministic for identical input
  - stable numeric `cluster.id` values across reruns are not required
- Startup cache values are available to dependent services.

### Phase 8: Route Risk Engine

Deliverables:

- Segment decomposition and factor calculations F1-F5.
- Shared scoring constants module (weights, thresholds, label bands) used by both:
  - route-risk computation
  - `GET /analytics/route-risk/scoring-model`
- Aggregate summary and risk labels.
- `GET /analytics/route-risk/scoring-model`.
- Cache-aware integration test strategy defined:
  - build startup caches from deterministic seeded fixture dataset
  - or inject deterministic cache overrides in test app startup

Exit criteria:

- Numeric tests for factor normalization and weighted score.
- Integration tests for F3-F5 using deterministic cache inputs (seeded or injected).
- Contract tests for response schema and status codes.

### Phase 9: Hardening and Final Documentation

Deliverables:

- Error-code catalog finalized.
- Performance checks for high-risk queries with explicit targets:
  - `GET /analytics/hotspots`: p95 < 800ms on full dataset
  - `GET /accidents` with `region_id` filter: p95 < 400ms
  - `POST /analytics/route-risk` for 10km route at 0.5km segments: p95 < 2.0s
- Performance measurement protocol documented:
  - measured against full imported dataset
  - local Docker PostgreSQL
  - single concurrent client
  - benchmark method and command recorded (for reproducibility in viva/report)
- README setup/run/testing docs.
- API documentation process finalized:
  - FastAPI OpenAPI generation as source of truth for implemented behavior
  - reconciliation pass against `docs/api-spec.md`
  - export path for submission artifacts documented

Exit criteria:

- Clean local setup from scratch.
- All tests green.
- Performance targets met or explicitly justified.
- Oral-demo flow rehearsable end-to-end.

## Testing Strategy

Test runner and isolation:

- `pytest` + async plugin (`pytest-asyncio` or `anyio`) with `httpx.AsyncClient`.
- Dedicated PostgreSQL test database.
- Migrations applied once per test session.
- Per-test isolation via transaction rollback/savepoint.
- Deterministic fixture loader for analytics and route-risk scenarios (implemented in Phase 1).
- Dedicated fixture profiles:
  - `minimal_crud`
  - `analytics_route_risk` (weather coverage gaps, cluster noise, and controlled time/speed distributions for F3/F4 expectations)
- Startup cache strategy for tests is explicit and deterministic:
  - build caches from seeded fixture data before app startup for cache-dependent suites
  - or inject deterministic cache overrides in app startup dependencies
  - do not rely on per-test rollback writes to mutate already-initialized startup caches

Minimum test layers:

- Unit tests for pure utility logic (banding, risk label mapping, score composition).
- Integration tests for endpoints (request/response/status/auth).
- Migration tests for schema assumptions.

Priority scenarios:

- Auth failures (`401`, `403`) and role boundaries.
- Count-field protections and CRUD side effects.
- MIDAS coverage and null weather observation handling.
- Route-risk math invariants (scores in `[0,1]`, expected weights).

## Security Checklist

- JWT signature and expiry verification.
- Strict Pydantic validation for all inputs.
- Parameterized SQLAlchemy queries only.
- No secrets in repo; environment-based configuration only.
- Consistent error envelopes without leaking internals.
- Dependency vulnerability scan before final submission.
- Token scopes/roles validated on every protected route.

## Documentation Workflow

At the end of each phase:

- Update relevant API examples if behavior changed.
- Update architecture notes when implementation deviates.
- Update `docs/development-plan.md` if phase boundaries, ordering, or scope changes.
- Record key decisions and tradeoffs for viva defense.

Final artifacts to keep aligned:

- `README.md`
- API documentation file(s)
- generated OpenAPI snapshot or export process notes
- technical report
- slides

## Definition of Done (Per Endpoint Group)

- Endpoint behavior matches `docs/api-spec.md`.
- Input validation and error responses are tested.
- Auth requirements are enforced where applicable.
- Query performance meets documented latency targets or is explicitly risk-accepted.
- Examples in docs are still accurate.

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

## Implementation Sequence

## Phase 0: Project Bootstrap

Deliverables:

- FastAPI app skeleton, configuration, dependency injection.
- SQLAlchemy async setup and session management.
- Alembic setup.
- Basic pytest and test database fixture.

Exit criteria:

- App starts locally.
- Health/basic route test passes.
- `alembic upgrade head` works.

## Phase 1: Core Schema and Migrations

Deliverables:

- Tables and indexes from `docs/architecture.md`.
- Post-creation FK constraints (`accident -> weather_observation`, `accident -> cluster`).
- Composite integrity for casualty to vehicle.

Exit criteria:

- Migration applies cleanly on empty DB.
- Migration downgrade/upgrade cycle passes once.
- Schema smoke tests pass.

## Phase 2: Auth and Security Baseline

Deliverables:

- JWT validation dependency.
- Role checks (`editor`, `admin`) for write routes.
- Standard error envelope for `401` and `403`.

Exit criteria:

- Unauthorized and forbidden integration tests pass.
- Write endpoints are protected; GET endpoints remain public.

## Phase 3: CRUD Foundation (Accident, Vehicle, Casualty)

Deliverables:

- Full CRUD endpoints per spec.
- Correct count maintenance for `number_of_vehicles` and `number_of_casualties`.
- Vehicle delete behavior that nulls linked casualty `vehicle_ref` first.
- `PATCH /accidents/:id` rejects count fields with `422`.

Exit criteria:

- Integration tests for all CRUD status paths.
- No router-level SQL; service-layer query logic only.

## Phase 4: Lookup and Relationship Endpoints

Deliverables:

- `GET /reference/conditions`
- Region and local-authority relationship endpoints.
- Scoped collection envelope behavior.

Exit criteria:

- Response shape tests pass for context/meta envelopes.
- Query parameter validation tests pass.

## Phase 5: Weather and Cluster Resources

Deliverables:

- Weather station endpoints.
- Cluster endpoints and scoped accidents-by-cluster.

Exit criteria:

- Coverage tests for nullable weather links and cluster noise points.
- Pagination and filtering behavior validated.

## Phase 6: Analytics Endpoints

Deliverables:

- Analytical endpoints excluding route risk.
- Zero-fill for accidents-by-time heatmap.
- Min-count protections for fatal-condition-combinations.
- MIDAS dimension support with `coverage_pct` handling.

Exit criteria:

- Deterministic query tests using fixed fixture data.
- Edge-case tests for empty/partial weather coverage.

## Phase 7: Route Risk Engine

Deliverables:

- Segment decomposition and factor calculations F1-F5.
- Aggregate summary and risk labels.
- `GET /analytics/route-risk/scoring-model`.

Exit criteria:

- Numeric tests for factor normalization and weighted score.
- Contract tests for response schema and status codes.

## Phase 8: Import Pipeline and Caching

Deliverables:

- STATS19 import.
- MIDAS matching without duplicate observation insertion.
- DBSCAN cluster generation and backfill.
- Cache preload and mutation-aware invalidation hooks.

Exit criteria:

- Import runs end-to-end on sample dataset.
- Re-run behavior is deterministic and documented.

## Phase 9: Hardening and Final Documentation

Deliverables:

- Performance checks on indexed queries.
- Error-code catalog finalized.
- README setup/run/testing docs.
- API documentation export and technical report alignment.

Exit criteria:

- Clean local setup from scratch.
- All tests green.
- Oral-demo flow rehearsable end-to-end.

## Testing Strategy

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

## Documentation Workflow

At the end of each phase:

- Update relevant API examples if behavior changed.
- Update architecture notes when implementation deviates.
- Record key decisions and tradeoffs for viva defense.

Final artifacts to keep aligned:

- `README.md`
- API documentation file(s)
- technical report
- slides

## Definition of Done (Per Endpoint Group)

- Endpoint behavior matches `docs/api-spec.md`.
- Input validation and error responses are tested.
- Auth requirements are enforced where applicable.
- Query performance is acceptable with documented indexes.
- Examples in docs are still accurate.

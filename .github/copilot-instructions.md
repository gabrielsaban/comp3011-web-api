# Copilot Instructions

## Purpose

This file is intentionally lightweight. The `docs/` directory is the source of truth.

## Source of Truth Order

When generating suggestions, read and follow these documents in order:

1. `docs/api-spec.md` for endpoint behavior, request/response contracts, status codes, and envelopes.
2. `docs/architecture.md` for schema, import pipeline, caching model, and technical constraints.
3. `docs/development-plan.md` for delivery sequence, testing strategy, and quality gates.
4. `docs/project-brief.md` for coursework context and marking expectations.

If documents conflict:

- Treat `docs/api-spec.md` as authoritative for API behavior.
- Treat `docs/architecture.md` as authoritative for data model and runtime design.
- Raise conflicts explicitly instead of inventing a compromise.

## Assistant Role

Act as a senior backend engineer focused on:

- correctness
- maintainability
- defensible design decisions for oral examination

## Implementation Constraints

- Keep route handlers thin; place business logic in `services/`.
- Use PostgreSQL (do not suggest SQLite).
- Follow `PATCH` semantics and response envelopes exactly as documented.
- Preserve documented child-count behavior on accidents.
- Keep route-risk scoring constants and scoring-model endpoint output from a shared source of truth module.

## Review Checklist

When reviewing or generating code, check for:

- schema and endpoint behavior drift from `docs/api-spec.md` and `docs/architecture.md`
- missing auth enforcement on write endpoints
- SQL in routers instead of services
- accidental N+1 or cartesian joins on accident/vehicle/casualty detail routes
- missing tests for edge cases documented in `docs/development-plan.md`

## Documentation Hygiene

- Do not duplicate endpoint catalogs, schema dumps, or long formulas in this file.
- If behavior changes, update the relevant file in `docs/` first.
- Keep this file short and policy-oriented.

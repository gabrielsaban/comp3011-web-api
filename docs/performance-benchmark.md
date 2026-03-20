# Performance Benchmark Protocol

This document defines the Phase 9 benchmark method used for reproducible local
latency checks.

## Scope

The benchmark script is `scripts/benchmark_phase9.py` and covers:

- `GET /api/v1/analytics/hotspots`
- `GET /api/v1/accidents` with `region_id` filter
- `POST /api/v1/analytics/route-risk` for a generated ~10km route

## Environment

- Dataset: full local import for project window (`2019-2023`)
- Database: local Docker PostgreSQL (`docker compose`)
- Client: single-concurrency in-process HTTP via `fastapi.testclient.TestClient`
- Caches: primed before measurement (`build_startup_caches`)

## Command

```bash
uv run python scripts/benchmark_phase9.py \
  --samples 30 \
  --warmup 5 \
  --output-json docs/phase9-benchmark-results.json
```

Optional metadata label:

```bash
uv run python scripts/benchmark_phase9.py --dataset-label "Local full import (2019-2023)"
```

Optional SQL diagnostics:

```bash
uv run python scripts/benchmark_phase9.py --verbose-sql
```

## Targets

- `hotspots`: p95 < `800ms`
- `accidents_region`: p95 < `400ms`
- `route_risk_10km`: p95 < `2000ms`

## Output

Script writes JSON results to `docs/phase9-benchmark-results.json` by default,
including:

- generation timestamp
- benchmark protocol metadata
- per-endpoint summary (`p50`, `p95`, mean, min, max, target, pass/fail)

## Interpretation

- `pass_target=true` indicates endpoint p95 meets Phase 9 target.
- If a target is missed, document the gap and justification in PR notes and
  include likely causes (hardware limits, dataset variance, or query plan issues).

# comp3011-web-api

UK Road Traffic Accidents REST API — COMP3011 coursework project.

Combines STATS19 accident records with MIDAS weather observations, DBSCAN spatial clustering, and a route risk scoring model.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for PostgreSQL)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd comp3011-web-api

# 2. Create your local env file and set a JWT secret
cp .env.example .env
# Edit .env and replace JWT_SECRET with any random string
# Optional: adjust CORS_ALLOW_ORIGINS if your frontend runs on a different origin

# 3. Start PostgreSQL
docker compose up -d

# 4. Install dependencies
uv sync --all-groups

# 5. Apply migrations
uv run alembic upgrade head
```

## Data Import (Phase 7+)

Validate source directories before loading:

```bash
uv run python scripts/import.py \
  --mode validate \
  --stats19-root /home/g/datasets/comp3011/stats19 \
  --lad-lookup "/home/g/datasets/comp3011/lad/Local_Authority_District_(April_2023)_to_(January_2021)Lookup.csv" \
  --midas-weather-root /home/g/datasets/comp3011/midas/hourly-weather \
  --midas-rain-root /home/g/datasets/comp3011/midas/hourly-rain
```

Run a full refresh import for the project window:

```bash
uv run python scripts/import.py \
  --mode run \
  --year-from 2019 --year-to 2023 \
  --stats19-root /home/g/datasets/comp3011/stats19 \
  --lad-lookup "/home/g/datasets/comp3011/lad/Local_Authority_District_(April_2023)_to_(January_2021)Lookup.csv" \
  --midas-weather-root /home/g/datasets/comp3011/midas/hourly-weather \
  --midas-rain-root /home/g/datasets/comp3011/midas/hourly-rain
```

## Running the API

```bash
uv run uvicorn app.main:app --reload
```

OpenAPI docs available at [http://localhost:8000/docs](http://localhost:8000/docs).

Startup caches for route-risk factors are preloaded by default
(`CACHE_PRELOAD_ON_STARTUP=true` in `.env.example`).

## Running Tests

The test suite requires the test database container:

```bash
docker compose up -d db_test
uv run pytest
```

## Linting and Type Checking

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

## Phase 9 Performance Benchmark

Run benchmark checks against your full local import:

```bash
uv run python scripts/benchmark_phase9.py \
  --samples 30 \
  --warmup 5 \
  --output-json docs/phase9-benchmark-results.json
```

Targets:

- `GET /api/v1/analytics/hotspots`: p95 < 800ms
- `GET /api/v1/accidents?region_id=<id>`: p95 < 400ms
- `POST /api/v1/analytics/route-risk` (about 10km route): p95 < 2.0s

See [docs/performance-benchmark.md](docs/performance-benchmark.md) for benchmark protocol details.

## OpenAPI Export and Reconciliation

Export the generated OpenAPI snapshot for submission artifacts:

```bash
uv run python scripts/export_openapi.py --output docs/openapi.snapshot.json
```

Reconciliation process and checklist are documented in
[docs/openapi-process.md](docs/openapi-process.md).

## Minting JWTs for Local Testing

Use the helper script to mint short-lived local tokens:

```bash
# editor token
uv run python scripts/mint_token.py --role editor

# admin token with custom subject and 15-minute expiry
uv run python scripts/mint_token.py --role admin --sub viva-demo --expires-minutes 15
```

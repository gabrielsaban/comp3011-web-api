# Deployment Guide

This guide covers a production-like local deployment using Docker Compose.

## Target Runtime Decision

Recommended target for this project: **single Linux VM (Docker Engine + Docker Compose)**.

Rationale:

- Directly matches the container topology already implemented (`api` + `db`).
- Lowest migration risk from local validation to hosted runtime.
- Predictable CPU/RAM and persistent volume behavior for PostgreSQL and startup caches.
- Simpler viva/demo operations than adapting to managed platform-specific constraints.

Platform mapping (local -> VM):

| Local workflow | VM workflow |
|---|---|
| `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build` | same command over SSH in `/opt/comp3011-web-api` |
| `uv run python scripts/smoke_deploy.py --base-url http://localhost:8000` | run from VM shell, or from your laptop against VM public URL |
| `docker compose ... logs -f api` | same command on VM for live diagnostics |
| `docker compose ... down` | same command on VM for controlled shutdown |

Suggested VM baseline:

- Ubuntu 24.04 LTS
- 2 vCPU / 4-8GB RAM
- 40GB+ SSD
- DNS + reverse proxy/TLS (for example Caddy or Nginx)

## 1) Prepare Environment

Copy the production environment template:

```bash
cp .env.prod.example .env.prod
```

Set at minimum:

- `JWT_SECRET` to a strong random value
- `POSTGRES_PASSWORD` to a non-default value
- `CORS_ALLOW_ORIGINS` if API and frontend are cross-origin

## 2) Build and Start

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

This brings up:

- `db` (PostgreSQL 16)
- `api` (FastAPI app, migrations run at container start)

## 3) Verify Health

```bash
curl -s http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Run smoke checks:

```bash
uv run python scripts/smoke_deploy.py --base-url http://localhost:8000
```

If imported data is loaded and you want deeper checks:

```bash
uv run python scripts/smoke_deploy.py --base-url http://localhost:8000 --check-analytics
```

## 4) Data Import (if required)

If this deployment uses a fresh DB, import data after startup:

```bash
uv run python scripts/import.py --mode run --year-from 2019 --year-to 2023 ...
```

Use the same source paths documented in `README.md`.

For VM runs, place datasets on attached storage and pass absolute VM paths:

```bash
uv run python scripts/import.py \
  --mode run \
  --year-from 2019 --year-to 2023 \
  --stats19-root /data/comp3011/stats19 \
  --lad-lookup "/data/comp3011/lad/Local_Authority_District_(April_2023)_to_(January_2021)Lookup.csv" \
  --midas-weather-root /data/comp3011/midas/hourly-weather \
  --midas-rain-root /data/comp3011/midas/hourly-rain
```

## 5) Operational Commands

View logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
```

Restart API:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml restart api
```

Stop stack:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

Stop and remove DB volume:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down -v
```

## 6) OpenAPI Export Artifact

Generate OpenAPI snapshot from running code:

```bash
uv run python scripts/export_openapi.py --output docs/openapi.snapshot.json
```

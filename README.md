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

# 3. Start PostgreSQL
docker compose up -d

# 4. Install dependencies
uv sync --all-groups

# 5. Apply migrations
uv run alembic upgrade head
```

## Running the API

```bash
uv run uvicorn app.main:app --reload
```

OpenAPI docs available at [http://localhost:8000/docs](http://localhost:8000/docs).

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

## Minting JWTs for Local Testing

Use the helper script to mint short-lived local tokens:

```bash
# editor token
uv run python scripts/mint_token.py --role editor

# admin token with custom subject and 15-minute expiry
uv run python scripts/mint_token.py --role admin --sub viva-demo --expires-minutes 15
```

# Copilot Instructions

## Context Sources

Before generating suggestions, refer to the following project documents in order:

1. `docs/project-brief.md` — coursework goals, constraints, and grading expectations
2. `docs/api-spec.md` — full REST API specification: all 43 endpoints, request/response schemas, parameter tables, and design conventions
3. `docs/architecture.md` — SQL DDL, import pipeline, DBSCAN parameters, route risk scoring formula, technology stack, application directory structure, and indexing strategy

---

## Project Summary

**UK Road Traffic Accidents API** — a data-driven REST API combining:

- **STATS19** DfT road safety data (~500,000 accident records, 2019–2023) with vehicles and casualties
- **MIDAS** Met Office hourly surface weather observations matched to accidents by proximity and time
- **DBSCAN** pre-computed spatial clusters (epsilon=0.89km, min_samples=10, haversine) labelled by severity
- **Route risk scoring** — POST endpoint accepting a polyline, returning per-segment risk scores from a 5-factor weighted model

Base URL: `/api/v1`
Total endpoints: 43 across six categories (CRUD, Weather Enrichment, Relationship, Cluster, Analytical, Route Risk).

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Database | PostgreSQL 15 |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Clustering | scikit-learn DBSCAN |
| Data import | pandas, NumPy |
| Testing | pytest + httpx |

Do not suggest SQLite — PostgreSQL is required for Haversine math functions (`SIN`, `COS`, `ASIN`, `SQRT`), used by the hotspots endpoint.

---

## Application Structure

```
app/
  main.py              # FastAPI app, startup event (cache initialisation)
  database.py          # async engine, get_db dependency
  models/              # SQLAlchemy ORM models (one file per table group)
  schemas/             # Pydantic v2 request/response models
  routers/             # FastAPI routers (accidents, vehicles, casualties,
                       #   regions, local_authorities, reference, clusters,
                       #   weather_stations, analytics)
  services/            # Business logic, query functions (keep routers thin)
  core/
    config.py          # settings (DATABASE_URL, etc.)
    cache.py           # startup caches: HEATMAP, SPEED_FATAL_RATES, P99_DENSITY
scripts/
  import.py            # full import pipeline: STATS19 -> MIDAS enrichment -> DBSCAN
migrations/            # Alembic migration files
tests/                 # pytest, httpx AsyncClient
docs/
  api-spec.md
  architecture.md
  project-brief.md
```

Keep route handlers thin. Business logic and SQL queries belong in `services/`.

---

## Database Schema Reference

Core tables:
- `accident` — primary fact table; `id` is TEXT (STATS19 reference e.g. `201801BS70001`); carries `cluster_id` FK and `weather_observation_id` FK; `number_of_vehicles` and `number_of_casualties` are **stored columns** (not computed on read), maintained by the application
- `vehicle` — child of accident; `(accident_id, vehicle_ref)` is a UNIQUE composite; `vehicle_ref` is a SMALLINT ordinal scoped within the accident (mirrors STATS19)
- `casualty` — child of accident; `(accident_id, casualty_ref)` UNIQUE; same ordinal pattern

Lookup tables (referenced by FK): `region`, `local_authority`, `severity`, `road_type`, `junction_detail`, `light_condition`, `weather_condition`, `road_surface`, `vehicle_type`

Extended tables:
- `weather_station` — MIDAS station metadata (id, name, lat, lng, elevation_m, active dates)
- `weather_observation` — hourly observations (station_id, observed_at, temperature_c, precipitation_mm, wind_speed_ms, visibility_m)
- `cluster` — DBSCAN output (centroid_lat/lng, radius_km, accident_count, fatal_count, serious_count, fatal_rate_pct, severity_label)

Key indexes (must be present for acceptable query performance):
`idx_accident_lat_lng`, `idx_accident_date`, `idx_accident_severity`, `idx_accident_la`, `idx_accident_cluster`, `idx_vehicle_accident`, `idx_casualty_accident`, `idx_obs_station_time`, `idx_cluster_centroid`

---

## API Design Conventions

### Response Envelopes

All responses use one of four envelope shapes:

**Collection** (paginated list):
```json
{
  "data": [...],
  "meta": { "total": 1240, "page": 1, "per_page": 25 }
}
```

**Single resource**:
```json
{ "data": { ... } }
```

**Scoped collection** (child resources under a parent — e.g. `/regions/:id/local-authorities`, `/clusters/:id/accidents`):
```json
{
  "context": { "id": 1, "name": "London" },
  "data": [...],
  "meta": { "total": 32 }
}
```

**Analytical** (aggregated results):
```json
{
  "query": { ...echo of request params... },
  "data": [...]
}
```

**Error**:
```json
{
  "error": {
    "status": 404,
    "code": "NOT_FOUND",
    "message": "Accident 2018XY00001 not found."
  }
}
```

### Path Parameters

- `:id` — primary key (integer or STATS19 text reference depending on resource)
- `:ref` — ordinal scoped within parent accident (e.g. `vehicle_ref`, `casualty_ref`); do not use a surrogate `id` column in the URL for vehicles or casualties

### Authentication and Authorization

- `GET` endpoints are public for coursework demo usage.
- Write endpoints under `/accidents` require `Authorization: Bearer <JWT>`.
- Role model:
  - `editor` can `POST` and `PATCH`
  - `admin` can `DELETE`
- Return `401` for missing/invalid token and `403` for insufficient role.

### Child Resource Counts

`number_of_vehicles` and `number_of_casualties` on `accident` are **maintained by the application**:
- Initialised to 0 on `POST /accidents`
- Incremented when a vehicle/casualty is added via `POST /accidents/:id/vehicles` or `...casualties`
- Decremented on `DELETE /accidents/:id/vehicles/:ref` or `...casualties/:ref`
- **Never recomputed with a COUNT subquery on read**
- Not patchable via `PATCH /accidents/:id`

### GET /accidents/:id — Two-Query Pattern

Do not JOIN vehicles and casualties in a single query when embedding both in the response. Use two separate queries to avoid M x N row multiplication:
```python
accident   = await db.get(Accident, accident_id)
vehicles   = await db.execute(select(Vehicle).where(Vehicle.accident_id == accident_id))
casualties = await db.execute(select(Casualty).where(Casualty.accident_id == accident_id))
```

### HTTP Semantics

- `POST /accidents/:id/vehicles` — `201 Created`, `Location` header
- `PATCH /accidents/:id` — partial update; return `422` if count fields are included in body
- `PATCH /accidents/:id/vehicles/:ref` — partial update of vehicle record
- `PATCH /accidents/:id/casualties/:ref` — partial update of casualty record
- `DELETE /accidents/:id/vehicles/:ref` — `204 No Content`
- On vehicle delete, set referencing `casualty.vehicle_ref` values to `NULL` in the same transaction before deleting the vehicle row
- `DELETE /accidents/:id/casualties/:ref` — `204 No Content`
- `POST /analytics/route-risk` — `200 OK` (computed analytical response; no persisted resource)

### Pagination

Default `per_page=25`, max `per_page=100`. Analytical endpoints do not paginate unless they return accident-level records (e.g. `/clusters/:id/accidents`).

---

## Analytical Endpoints: Implementation Notes

### GET /analytics/accidents-by-time

Returns a 24x7 heatmap (168 cells). SQL `GROUP BY` cannot produce zero-count rows for missing combinations. Zero-fill in Python after the query:

```python
result = {(row.day_of_week, row.hour): row.count for row in rows}
grid = [
    {"day_of_week": d, "hour": h, "accident_count": result.get((d, h), 0)}
    for d in range(1, 8) for h in range(0, 24)
]
```

### GET /analytics/severity-by-conditions

Supports both STATS19 dimensions (`weather_condition_id`, `road_surface_id`, `light_condition_id`, `junction_detail_id`, `speed_limit`, `urban_or_rural`) and MIDAS dimensions (`precipitation_band`, `visibility_band`, `temperature_band`).

MIDAS dimensions require a JOIN to `weather_observation` via `accident.weather_observation_id`. Use conditional query builder branching on the `dimension` parameter. When a MIDAS dimension is requested, only accidents with a non-NULL `weather_observation_id` are included — report actual coverage via `coverage_pct` in the response.

MIDAS band definitions:
- `precipitation_band`: Dry (<0.2mm), Light (0.2-2mm), Moderate (2-10mm), Heavy (>10mm)
- `visibility_band`: Dense Fog (<100m), Fog (100-1000m), Mist (1000-5000m), Clear (>5000m)
- `temperature_band`: Freezing (<=0C), Cold (0-7C), Mild (7-15C), Warm (>15C)

### GET /analytics/hotspots

Uses PostgreSQL Haversine with a bounding-box pre-filter index scan, then exact distance check in the SELECT clause. Do not include `nearest_accident_km` — that requires a correlated subquery per grid cell and is too expensive. Direct clients to `GET /clusters` for primary spatial querying.

### GET /analytics/fatal-condition-combinations

Apply `HAVING COUNT(*) >= :min_count` (default 10) to suppress statistically unreliable combinations. Without this, single-accident combinations appear at 100% fatal rate.

### POST /analytics/route-risk — Scoring Model

Decompose the route into segments of `segment_length_km` (default 0.5km). Per segment:

```
risk_score = 0.35*F1 + 0.30*F2 + 0.15*F3 + 0.10*F4 + 0.10*F5
```

| Factor | Formula | Data source |
|--------|---------|-------------|
| F1 accident_density | `min(density / P99_DENSITY, 1.0)` | SQL bounding box + Python Haversine |
| F2 severity_score | `(3*fatal + 2*serious + 1*slight) / (3*total)` | same SQL result |
| F3 time_risk | `HEATMAP[day_of_week][hour] / max(HEATMAP)` | startup cache |
| F4 speed_limit_risk | `fatal_rate_pct[dominant_speed_limit] / max(SPEED_FATAL_RATES)` | startup cache |
| F5 cluster_proximity | 1.0 inside cluster, linear decay to 0 over 2km beyond cluster edge | cluster table |

Populate startup caches in `app/main.py` on the `startup` event:
- `HEATMAP`: `{(day_of_week, hour): count}` from `SELECT day_of_week, EXTRACT(hour FROM time), COUNT(*) FROM accident GROUP BY 1, 2`
- `SPEED_FATAL_RATES`: `{speed_limit: fatal_rate_pct}` from severity aggregation grouped by speed limit
- `P99_DENSITY`: scalar float — compute accident density per 1km2 grid cell over all accidents, take 99th percentile

Risk labels: Very Low (0-0.2), Low (0.2-0.4), Moderate (0.4-0.6), High (0.6-0.8), Critical (0.8-1.0).

---

## DBSCAN Import

Run at the end of the import pipeline after all accidents are loaded:

```python
from sklearn.cluster import DBSCAN
import numpy as np

coords = np.radians([[a.latitude, a.longitude] for a in all_accidents if a.latitude is not None])
db = DBSCAN(eps=0.89/6371.0, min_samples=10, algorithm='ball_tree', metric='haversine').fit(coords)
```

`severity_label` thresholds on `fatal_rate_pct`: >5% Critical, 2-5% High, 1-2% Medium, <=1% Low.

After writing cluster rows, bulk-update `accident.cluster_id`. Accidents with `label == -1` (noise) retain `cluster_id = NULL`.

---

## MIDAS Enrichment

For each accident, find the nearest station with an observation within +/-1 hour:
1. Candidate stations within 30km (bounding-box pre-filter)
2. Exact Haversine; select nearest station
3. Find closest observation where `|observed_at - accident_datetime| <= 60 minutes`
4. Set `accident.weather_observation_id = observation.id`

Run as a bulk step during import, not at query time. Unmatched accidents (~15%) retain `weather_observation_id = NULL`.

---

## Development Priorities

Suggestions should favour:

- clear and simple architecture
- readable, maintainable code
- conventional REST API design
- sensible database modelling
- solutions that can be easily explained in a coursework oral presentation

Avoid unnecessary complexity or premature optimisation.

---

## Review Checklist

When reviewing code or design:

- flag any COUNT subquery on `number_of_vehicles`/`number_of_casualties` — use maintained stored columns
- flag triple JOIN of accident x vehicle x casualty — use the two-query pattern instead
- flag SQLite usage — project requires PostgreSQL
- flag Haversine radius queries missing a bounding-box pre-filter
- flag missing startup cache initialisation for route risk factors
- flag `PATCH` handlers that accept count fields
- ensure scoped collection envelope is used for parent-scoped child resources
- flag `PUT` where `PATCH` is specified
- flag `fatal-condition-combinations` queries missing `HAVING COUNT(*) >= :min_count`
- flag `accidents-by-time` results missing the Python-side zero-fill step

---

## AI Behaviour Constraints

Stay within the scope defined in `docs/api-spec.md` and `docs/architecture.md`. Do not add endpoints, fields, or tables not specified in those documents unless explicitly instructed.

All design decisions must be defensible in a coursework oral presentation. Prefer explainability over cleverness.

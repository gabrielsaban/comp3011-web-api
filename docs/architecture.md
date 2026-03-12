# Architecture — UK Road Traffic Accidents API

## 1. Project Overview

A FastAPI + PostgreSQL REST API that exposes the STATS19 UK road safety dataset enriched with Met Office MIDAS atmospheric observations. The system extends standard accident retrieval with three analytical layers: **MIDAS weather enrichment**, **DBSCAN spatial clustering**, and **route risk scoring**.

The core question the API is designed to answer is: *how dangerous is a given road, at a given time, under current conditions?* Each capability layer contributes a component of that answer.

---

## 2. Data Sources

### 2.1 STATS19 — Department for Transport

- **URL:** https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-safety-data
- **Coverage:** All reported personal injury road accidents in Great Britain, 2019–2023
- **Volume:** ~500,000 accident records, ~600,000 vehicle records, ~650,000 casualty records
- **Format:** CSV (three separate files per year: accidents, vehicles, casualties)
- **Licence:** Open Government Licence v3.0

Key fields used: accident index (primary key), date, time, latitude, longitude, severity, local authority, road type, junction detail, light condition, weather condition, road surface, speed limit, urban/rural, police attended, number of vehicles, number of casualties.

### 2.2 Met Office MIDAS — UK Met Office / CEDA Archive

- **URL:** https://catalogue.ceda.ac.uk/uuid/220a65615218d5c9cc9e4785a3234bd0
- **Coverage:** Hourly surface observations from ~350 UK weather stations, 2019–2023
- **Fields used:** Air temperature (°C), precipitation accumulation (mm/hr), mean wind speed (m/s), horizontal visibility (m)
- **Format:** CSV (one file per station per year)
- **Licence:** Open Government Licence v3.0 (free CEDA account registration required)
- **Matching strategy:** For each accident, find the nearest active MIDAS station within 30km using the Haversine formula, then select the observation whose timestamp is closest to the accident time (within ±1 hour). Matched observations are stored in `weather_observation`; accidents with no station within 30km or no observation within the time window receive `weather_observation_id = NULL`. Expected coverage: ~85% of accidents.

---

## 3. Database Schema

### 3.1 Entity Relationship Summary

```
region ──< local_authority ──< accident >── severity
                                    │
                         ┌──────────┼──────────────────┐
                         │          │                   │
                       vehicle   casualty     weather_observation
                                                    │
                                              weather_station

accident >── road_type
accident >── junction_detail
accident >── light_condition
accident >── weather_condition      (STATS19 categorical code)
accident >── road_surface
accident >── cluster                (nullable — NULL if DBSCAN noise point)
vehicle  >── vehicle_type
casualty >── severity
```

### 3.2 Lookup Tables

```sql
CREATE TABLE region (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE local_authority (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    region_id INTEGER NOT NULL REFERENCES region(id)
);

CREATE TABLE severity (
    id    INTEGER PRIMARY KEY,  -- 1=Fatal, 2=Serious, 3=Slight
    label TEXT NOT NULL
);

CREATE TABLE road_type (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE junction_detail (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE light_condition (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE weather_condition (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE road_surface (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE vehicle_type (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);
```

### 3.3 Core Tables

```sql
CREATE TABLE accident (
    id                     TEXT PRIMARY KEY,     -- STATS19 accident index e.g. '2022010012345'
    date                   DATE NOT NULL,
    time                   TIME,
    day_of_week            SMALLINT,             -- 1 (Sunday) to 7 (Saturday)
    latitude               DOUBLE PRECISION,
    longitude              DOUBLE PRECISION,
    local_authority_id     INTEGER REFERENCES local_authority(id),
    severity_id            INTEGER NOT NULL REFERENCES severity(id),
    road_type_id           INTEGER REFERENCES road_type(id),
    junction_detail_id     INTEGER REFERENCES junction_detail(id),
    light_condition_id     INTEGER REFERENCES light_condition(id),
    weather_condition_id   INTEGER REFERENCES weather_condition(id),
    road_surface_id        INTEGER REFERENCES road_surface(id),
    speed_limit            SMALLINT,
    urban_or_rural         TEXT,                 -- 'Urban', 'Rural', 'Unallocated'
    police_attended        BOOLEAN,
    number_of_vehicles     SMALLINT NOT NULL DEFAULT 0,
    number_of_casualties   SMALLINT NOT NULL DEFAULT 0,
    -- Set during post-import enrichment steps. FK constraints are added
    -- after dependent tables are created (see Section 3.6).
    weather_observation_id INTEGER,
    cluster_id             INTEGER
);

CREATE TABLE vehicle (
    id                 SERIAL PRIMARY KEY,
    accident_id        TEXT NOT NULL REFERENCES accident(id) ON DELETE CASCADE,
    vehicle_ref        SMALLINT NOT NULL,        -- ordinal within accident (1-based)
    vehicle_type_id    INTEGER REFERENCES vehicle_type(id),
    age_of_driver      SMALLINT,
    sex_of_driver      TEXT,
    engine_capacity_cc INTEGER,
    propulsion_code    TEXT,
    age_of_vehicle     SMALLINT,
    journey_purpose    TEXT,
    UNIQUE(accident_id, vehicle_ref)
);

CREATE TABLE casualty (
    id             SERIAL PRIMARY KEY,
    accident_id    TEXT NOT NULL REFERENCES accident(id) ON DELETE CASCADE,
    vehicle_ref    SMALLINT,                     -- links to vehicle in same accident
    casualty_ref   SMALLINT NOT NULL,            -- ordinal within accident (1-based)
    severity_id    INTEGER NOT NULL REFERENCES severity(id),
    casualty_class TEXT,                         -- 'Driver', 'Passenger', 'Pedestrian'
    casualty_type  TEXT,
    sex            TEXT,
    age            SMALLINT,
    age_band       TEXT,                         -- derived from age on insert
    CONSTRAINT fk_casualty_vehicle_ref
        FOREIGN KEY (accident_id, vehicle_ref)
        REFERENCES vehicle(accident_id, vehicle_ref)
        DEFERRABLE INITIALLY IMMEDIATE,
    UNIQUE(accident_id, casualty_ref)
);
```

When deleting a vehicle through the API, any matching `casualty.vehicle_ref` values are set to `NULL` in the same transaction before the vehicle row is deleted, preserving referential integrity.

### 3.4 Weather Enrichment Tables

```sql
CREATE TABLE weather_station (
    id           INTEGER PRIMARY KEY,            -- MIDAS src_id
    name         TEXT NOT NULL,
    latitude     DOUBLE PRECISION NOT NULL,
    longitude    DOUBLE PRECISION NOT NULL,
    elevation_m  INTEGER,
    active_from  DATE,
    active_to    DATE                            -- NULL if still active
);

CREATE TABLE weather_observation (
    id                SERIAL PRIMARY KEY,
    station_id        INTEGER NOT NULL REFERENCES weather_station(id),
    observed_at       TIMESTAMP NOT NULL,        -- UTC timestamp
    temperature_c     REAL,
    precipitation_mm  REAL,                      -- hourly accumulation mm
    wind_speed_ms     REAL,                      -- mean wind speed m/s
    visibility_m      INTEGER
);

CREATE INDEX idx_obs_station_time ON weather_observation(station_id, observed_at);
```

`station_distance_km` exposed by `GET /accidents/:id` is computed at read time from accident and station coordinates; it is not persisted as a column.

### 3.5 Cluster Table

```sql
CREATE TABLE cluster (
    id             SERIAL PRIMARY KEY,
    centroid_lat   DOUBLE PRECISION NOT NULL,
    centroid_lng   DOUBLE PRECISION NOT NULL,
    radius_km      REAL NOT NULL,
    accident_count INTEGER NOT NULL,
    fatal_count    INTEGER NOT NULL DEFAULT 0,
    serious_count  INTEGER NOT NULL DEFAULT 0,
    fatal_rate_pct REAL NOT NULL,
    severity_label TEXT NOT NULL               -- 'Low', 'Medium', 'High', 'Critical'
);
```

### 3.6 Post-Creation Foreign Keys

```sql
ALTER TABLE accident
    ADD CONSTRAINT fk_accident_weather_observation
    FOREIGN KEY (weather_observation_id) REFERENCES weather_observation(id);

ALTER TABLE accident
    ADD CONSTRAINT fk_accident_cluster
    FOREIGN KEY (cluster_id) REFERENCES cluster(id);
```

---

## 4. Data Import Pipeline

The import is a standalone script (`scripts/import.py`) run once before the API starts. It is idempotent — re-running truncates all tables and reloads from source files.

```
STATS19 CSVs (2019–2023)         MIDAS CSVs (2019–2023)
         │                                │
         ▼                                ▼
   parse_stats19()               parse_midas_stations()
         │                                │
         ▼                                ▼
   load_lookups()                load_stations()
         │                                │
         ▼                                ▼
   load_accidents()              load_observations()
         │                                │
         └─────────────┬──────────────────┘
                       ▼
               enrich_accidents()         ← MIDAS station matching
                       │
                       ▼
               run_dbscan()               ← scikit-learn DBSCAN
                       │
                       ▼
               write_clusters()           ← populate cluster table
                       │
                       ▼
               update_accident_clusters() ← set accident.cluster_id
                       │
                       ▼
               compute_cache_values()     ← P99 density, heatmap, speed rates
```

### 4.1 STATS19 Import

1. For each year, read `accidents_YYYY.csv`, `vehicles_YYYY.csv`, `casualties_YYYY.csv`.
2. Upsert lookup values (severity codes, condition codes, etc.) into lookup tables.
3. Resolve or insert `region` and `local_authority` rows; set `local_authority_id`.
4. Bulk-insert accident rows using `INSERT ... ON CONFLICT DO NOTHING` to handle re-runs.
5. Insert vehicle rows with auto-assigned `vehicle_ref` (sequential per accident).
6. Insert casualty rows; compute `age_band` from `age` during insert using STATS19 standard bands:

```python
def age_band(age: int | None) -> str | None:
    if age is None: return None
    bands = [(0,5,'0-5'),(6,10,'6-10'),(11,15,'11-15'),(16,20,'16-20'),
             (21,25,'21-25'),(26,35,'26-35'),(36,45,'36-45'),(46,55,'46-55'),
             (56,65,'56-65'),(66,75,'66-75')]
    for lo, hi, label in bands:
        if lo <= age <= hi: return label
    return '76+'
```

### 4.2 MIDAS Enrichment

For each accident with a non-null latitude and longitude:

1. Load all `weather_station` rows into a numpy array of `[lat, lng]` on script startup.
2. Compute Haversine distances from the accident to all stations (vectorised in NumPy).
3. Filter to stations within 30km and active on the accident's date.
4. Select the nearest remaining station.
5. Query `weather_observation` for that station where `|observed_at - accident_datetime| <= 1 hour`.
6. Pick the observation with the smallest time delta.
7. If found, set `accident.weather_observation_id` to the selected observation row (no duplicate weather observation rows are inserted during enrichment).

This runs in a single pass over sorted accidents, batching DB writes with `executemany`.

### 4.3 DBSCAN Cluster Computation

```python
from sklearn.cluster import DBSCAN
import numpy as np

coords = np.radians([[a.latitude, a.longitude] for a in all_accidents
                     if a.latitude is not None])

db = DBSCAN(
    eps=0.89 / 6371.0,   # 890m in radians
    min_samples=10,
    algorithm='ball_tree',
    metric='haversine'
).fit(coords)
```

For each unique label ≥ 0 (noise points have label −1):

1. Collect member accidents.
2. Compute centroid as the mean latitude and longitude of members.
3. Compute `radius_km` as the 95th-percentile Haversine distance from centroid to members.
4. Aggregate severity counts and compute `fatal_rate_pct`.
5. Assign `severity_label`:
   - **Critical**: `fatal_rate_pct > 5.0`
   - **High**: `2.0 < fatal_rate_pct ≤ 5.0`
   - **Medium**: `1.0 < fatal_rate_pct ≤ 2.0`
   - **Low**: `fatal_rate_pct ≤ 1.0`
6. Insert into `cluster`; update `accident.cluster_id` for all members.

**Parameter justification:**

| Parameter | Value | Rationale |
|---|---|---|
| `epsilon` | 890m | Matches a typical urban junction catchment area. Smaller values over-fragment; larger values merge separate junctions. |
| `min_samples` | 10 | Over 5 years, 10 accidents at one location is a reliable signal of a systemic problem rather than chance co-location. |
| `metric` | haversine | Spherical distance is required at UK latitudes (~51–53°N) where 1° longitude ≈ 64km but 1° latitude ≈ 111km. |
| `algorithm` | ball_tree | Required for custom distance metrics in scikit-learn. |

---

## 5. Route Risk Scoring Model

### 5.1 Segment Decomposition

The input route (array of `[lat, lng]` waypoints) is interpolated into segments of fixed length `L` km (default 0.5km) using linear interpolation between consecutive waypoints. The midpoint of each segment serves as the spatial anchor for factor computation.

### 5.2 Scoring Factors

All five factors are normalised to `[0, 1]` before weighting.

**F1 — Accident Density**

Measures the concentration of historical accidents around the segment midpoint.

```
density(p) = COUNT(accidents within buffer_radius of p) / (π · r²)   [accidents/km²]

F1 = min(density(p) / P99_density, 1.0)
```

`P99_density` is the 99th percentile of `density` computed across all 500m × 500m grid cells covering the UK road network. It is computed once during import and stored in `app/core/cache.py`. Capping at P99 prevents extreme outlier junctions from compressing every other score toward zero.

**F2 — Severity Score**

Captures the injury severity of accidents near the segment, independent of count.

```
F2 = (3·fatal + 2·serious + 1·slight) / (3 · total_in_buffer)
```

Returns 0.0 when no accidents are in the buffer; 1.0 in the theoretical extreme of all-fatal accidents.

**F3 — Time Risk**

Looked up from the `HEATMAP` cache (loaded from the `accidents-by-time` query result on startup).

```
F3 = HEATMAP[day_of_week][hour_of_day] / max(HEATMAP)
```

Captures that Friday evening rush hour is genuinely riskier than 3am on a Tuesday.

**F4 — Speed Limit Risk**

The dominant `speed_limit` among accidents in the buffer is determined. Its `fatal_rate_pct` is looked up from the `SPEED_FATAL_RATES` cache (from `severity-by-speed-limit` data).

```
F4 = fatal_rate_pct[dominant_speed_limit] / max(SPEED_FATAL_RATES.values())
```

**F5 — Cluster Proximity**

Rewards being near a known high-density cluster even if the immediate buffer of the segment alone is sparse.

```
if midpoint is within any cluster's radius_km:
    F5 = 1.0
else:
    d_km = min Haversine distance from midpoint to nearest cluster edge
    F5 = max(0.0, 1.0 - d_km / 2.0)   # linear decay over 2km beyond cluster edge
```

### 5.3 Composite Score

```
risk_score = 0.35·F1 + 0.30·F2 + 0.15·F3 + 0.10·F4 + 0.10·F5
```

| Factor | Weight | Rationale |
|---|---|---|
| Accident density (F1) | 0.35 | Primary indicator — a location is dangerous if accidents have repeatedly occurred there |
| Severity score (F2) | 0.30 | Distinguishes high-volume/low-severity urban locations from low-volume/high-severity rural roads |
| Time risk (F3) | 0.15 | Temporal context is meaningful but secondary to the location's inherent history |
| Speed limit risk (F4) | 0.10 | Correlates with injury potential; lower weight because speed limit is often constant along a route segment |
| Cluster proximity (F5) | 0.10 | Encodes spatial concentration at a scale broader than the immediate buffer |

### 5.4 Risk Labels

| Score | Label |
|---|---|
| 0.0–0.2 | Very Low |
| 0.2–0.4 | Low |
| 0.4–0.6 | Moderate |
| 0.6–0.8 | High |
| 0.8–1.0 | Critical |

### 5.5 Aggregate Route Score

```
aggregate_risk_score = mean(segment_scores)
```

The mean is used rather than the maximum to represent the overall journey. The worst segment is surfaced separately as `peak_segment_risk` and `peak_segment_id`.

---

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| API framework | FastAPI | Async-native, automatic OpenAPI/Swagger docs, Pydantic v2 validation |
| ORM | SQLAlchemy 2.x (core + declarative) | Explicit query control avoids N+1 patterns; `select()` with `selectinload` for child relations |
| Database | PostgreSQL 15 | Required for Haversine math functions (`SIN`, `COS`, `ASIN`, `SQRT`) used in hotspot queries |
| Migrations | Alembic | Schema versioning; migration files committed to source control |
| Data processing | pandas, NumPy | CSV parsing, vectorised MIDAS station matching during import |
| Clustering | scikit-learn | `DBSCAN` with `ball_tree` / `haversine` metric |
| Validation | Pydantic v2 | Request and response schema enforcement |
| Testing | pytest + httpx | Async integration tests against an isolated test database |
| Config | python-dotenv / pydantic-settings | `DATABASE_URL`, `MIDAS_DATA_PATH`, `STATS19_DATA_PATH` |

---

## 7. Application Structure

```
comp3011-web-api/
├── app/
│   ├── main.py                  # App factory, router registration, startup cache load
│   ├── database.py              # Async SQLAlchemy engine + session dependency
│   ├── models/
│   │   ├── accident.py          # Accident, Vehicle, Casualty ORM models
│   │   ├── cluster.py           # Cluster ORM model
│   │   ├── weather.py           # WeatherStation, WeatherObservation ORM models
│   │   └── lookups.py           # Region, LocalAuthority, Severity, etc.
│   ├── schemas/
│   │   ├── accident.py          # Pydantic request/response schemas
│   │   ├── cluster.py
│   │   ├── weather.py
│   │   └── route_risk.py        # RouteRiskRequest, RouteRiskResponse
│   ├── routers/
│   │   ├── accidents.py         # /accidents CRUD routes
│   │   ├── regions.py           # /regions, /local-authorities routes
│   │   ├── clusters.py          # /clusters routes
│   │   ├── weather_stations.py  # /weather-stations routes
│   │   ├── analytics.py         # /analytics/* routes
│   │   └── route_risk.py        # /analytics/route-risk routes
│   ├── services/
│   │   ├── accident_service.py  # Query construction for accident endpoints
│   │   ├── cluster_service.py   # Cluster queries
│   │   ├── analytics_service.py # Aggregation queries
│   │   └── route_risk_service.py# Segment decomposition + scoring
│   └── core/
│       ├── config.py            # Settings model
│       └── cache.py             # HEATMAP, SPEED_FATAL_RATES, P99_DENSITY
├── scripts/
│   └── import.py                # STATS19 + MIDAS import + DBSCAN pipeline
├── migrations/                  # Alembic migration files
├── tests/
│   ├── conftest.py
│   ├── test_accidents.py
│   ├── test_clusters.py
│   ├── test_analytics.py
│   └── test_route_risk.py
└── docs/
    ├── api-spec.md
    └── architecture.md
```

**Handler pattern:** Route handlers are thin — they validate input via Pydantic and delegate to a service function. No SQL lives in handlers.

```python
# routers/route_risk.py
@router.post("/analytics/route-risk", status_code=200, response_model=RouteRiskResponse)
async def score_route(
    body: RouteRiskRequest,
    db: AsyncSession = Depends(get_db)
) -> RouteRiskResponse:
    return await route_risk_service.score(db, body)
```

---

## 8. Performance Considerations

### 8.1 Database Indexes

```sql
-- Spatial filters (used by hotspot queries and route risk bounding box)
CREATE INDEX idx_accident_lat        ON accident(latitude);
CREATE INDEX idx_accident_lng        ON accident(longitude);
CREATE INDEX idx_accident_lat_lng    ON accident(latitude, longitude);

-- Common filter columns
CREATE INDEX idx_accident_date       ON accident(date);
CREATE INDEX idx_accident_severity   ON accident(severity_id);
CREATE INDEX idx_accident_la         ON accident(local_authority_id);
CREATE INDEX idx_accident_cluster    ON accident(cluster_id);
CREATE INDEX idx_accident_obs        ON accident(weather_observation_id);

-- Child table joins
CREATE INDEX idx_vehicle_accident    ON vehicle(accident_id);
CREATE INDEX idx_casualty_accident   ON casualty(accident_id);

-- Weather observation time-series lookup
CREATE INDEX idx_obs_station_time    ON weather_observation(station_id, observed_at);

-- Cluster centroid lookup for proximity queries
CREATE INDEX idx_cluster_centroid    ON cluster(centroid_lat, centroid_lng);
```

### 8.2 Route Risk Query Strategy

The buffer radius query for each segment midpoint uses two stages:

**Stage 1 — SQL bounding box** (uses `idx_accident_lat_lng`):
```sql
SELECT id, latitude, longitude, severity_id, speed_limit
FROM accident
WHERE latitude  BETWEEN :lat - :delta AND :lat + :delta
  AND longitude BETWEEN :lng - :delta AND :lng + :delta
```
where `delta = buffer_radius_km / 111.0` degrees.

**Stage 2 — Python Haversine filter** on the returned row set (~tens to low hundreds of rows after bounding box). The exact radius check is applied in the service layer, not in SQL. This avoids the PostgreSQL math function dependency for this inner loop.

For a 10km route at 0.5km segments (20 segments), total query count is 20 bounding box queries. Each typically returns fewer than 200 rows before Haversine filtering.

### 8.3 N+1 Prevention for `GET /accidents/:id`

The single-accident endpoint embeds both `vehicles` and `casualties`. To avoid a cartesian product from joining all three tables simultaneously, the implementation issues **two child queries** after fetching the accident row:

```python
async def get_accident_detail(db: AsyncSession, accident_id: str):
    accident = await db.get(Accident, accident_id)
    if not accident:
        raise HTTPException(404)
    vehicles = (await db.execute(
        select(Vehicle).where(Vehicle.accident_id == accident_id)
    )).scalars().all()
    casualties = (await db.execute(
        select(Casualty).where(Casualty.accident_id == accident_id)
    )).scalars().all()
    return build_response(accident, vehicles, casualties)
```

### 8.4 Startup Cache Strategy

Three values are precomputed during import and loaded into module-level memory on API startup:

| Cache key | Source | Used in |
|---|---|---|
| `HEATMAP[day][hour]` | `accidents-by-time` GROUP BY result | Route risk F3 |
| `SPEED_FATAL_RATES[speed_limit]` | `severity-by-speed-limit` result | Route risk F4 |
| `P99_DENSITY` | 99th-percentile computation over grid cells | Route risk F1 normalisation |

Cache policy:

- Caches are loaded once on startup from the current database state.
- Runtime writes to CRUD endpoints do not trigger in-process recomputation hooks for these global aggregates.
- Cache refresh occurs on process restart (including after full dataset re-import).

Analytical endpoints that aggregate the full dataset (`annual-trend`, `seasonal-pattern`, `accidents-by-local-authority`) can additionally use response-level caching with a TTL keyed by query parameter hash.

## 9. Security and Authorization

Authentication is enforced at the API layer using JWT bearer tokens (`Authorization: Bearer <token>`).

- `GET` endpoints are public for presentation/demo use.
- Write endpoints under `/accidents` require authentication.
- Role-based authorization:
  - `editor`: `POST` and `PATCH`
  - `admin`: `DELETE`
- Unauthorized requests return `401`; forbidden requests return `403`.

This model keeps analytical exploration easy during demos while protecting data integrity for mutating operations.

---

## 10. External Dependencies

The API has **no runtime external API calls**. All data is imported into local PostgreSQL before the server starts.

| Dependency | When | Authentication |
|---|---|---|
| data.gov.uk (STATS19 CSVs) | Import time only | None |
| CEDA archive (MIDAS CSVs) | Import time only | Free account registration |
| scikit-learn | Import time only (DBSCAN) | N/A — local Python package |

This ensures the API runs fully offline after import, satisfying the coursework requirement to be runnable locally without external services.

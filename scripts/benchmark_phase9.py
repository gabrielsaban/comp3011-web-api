from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from statistics import mean
from time import perf_counter
from typing import Protocol

from httpx import ASGITransport, AsyncClient

from app.core.cache import build_startup_caches
from app.database import AsyncSessionLocal, engine
from app.main import app

TARGETS_MS = {
    "hotspots": 800.0,
    "accidents_region": 400.0,
    "route_risk_10km": 2000.0,
}


class HttpResponse(Protocol):
    status_code: int


@dataclass(slots=True)
class BenchmarkSummary:
    name: str
    samples: int
    warmup: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    target_ms: float
    pass_target: bool


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    weight = rank - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


async def _measure(
    name: str,
    call: Callable[[], Awaitable[HttpResponse]],
    samples: int,
    warmup: int,
) -> BenchmarkSummary:
    for _ in range(warmup):
        response = await call()
        if response.status_code != 200:
            raise RuntimeError(f"{name} warmup failed: status={response.status_code}")

    timings_ms: list[float] = []
    for _ in range(samples):
        started = perf_counter()
        response = await call()
        elapsed_ms = (perf_counter() - started) * 1000.0
        if response.status_code != 200:
            raise RuntimeError(f"{name} failed: status={response.status_code}")
        timings_ms.append(elapsed_ms)

    p50_ms = _percentile(timings_ms, 0.50)
    p95_ms = _percentile(timings_ms, 0.95)
    target_ms = TARGETS_MS[name]
    return BenchmarkSummary(
        name=name,
        samples=samples,
        warmup=warmup,
        p50_ms=round(p50_ms, 2),
        p95_ms=round(p95_ms, 2),
        mean_ms=round(mean(timings_ms), 2),
        min_ms=round(min(timings_ms), 2),
        max_ms=round(max(timings_ms), 2),
        target_ms=target_ms,
        pass_target=p95_ms <= target_ms,
    )


async def _prime_startup_caches() -> None:
    async with AsyncSessionLocal() as session:
        await build_startup_caches(session)


async def _find_first_region_id(client: AsyncClient) -> int:
    response = await client.get("/api/v1/regions")
    if response.status_code != 200:
        raise RuntimeError("Unable to fetch regions for benchmark setup.")
    rows = response.json()["data"]
    if not rows:
        raise RuntimeError("No regions found in dataset.")
    return int(rows[0]["id"])


async def _find_first_geocoded_accident(client: AsyncClient) -> tuple[float, float]:
    response = await client.get(
        "/api/v1/accidents",
        params={"page": 1, "per_page": 100, "sort": "date"},
    )
    if response.status_code != 200:
        raise RuntimeError("Unable to fetch accidents for benchmark setup.")
    for row in response.json()["data"]:
        lat = row.get("latitude")
        lng = row.get("longitude")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    raise RuntimeError("No geocoded accident found for benchmark setup.")


def _build_route_payload(origin_lat: float, origin_lng: float) -> dict[str, object]:
    # ~10km eastward polyline at UK latitudes.
    waypoints = [
        [origin_lat, origin_lng],
        [origin_lat, origin_lng + 0.05],
        [origin_lat, origin_lng + 0.10],
        [origin_lat, origin_lng + 0.145],
    ]
    return {
        "waypoints": waypoints,
        "options": {
            "time_of_day": "08:30",
            "day_of_week": 2,
            "segment_length_km": 0.5,
            "buffer_radius_km": 0.5,
        },
    }


async def _run_benchmark(samples: int, warmup: int, verbose_sql: bool) -> list[BenchmarkSummary]:
    previous_echo = engine.sync_engine.echo
    if not verbose_sql:
        engine.sync_engine.echo = False

    try:
        await _prime_startup_caches()

        transport = ASGITransport(app=app, raise_app_exceptions=True)
        async with AsyncClient(transport=transport, base_url="http://benchmark") as client:
            region_id = await _find_first_region_id(client)
            lat, lng = await _find_first_geocoded_accident(client)
            route_payload = _build_route_payload(lat, lng)

            return [
                await _measure(
                    "hotspots",
                    lambda: client.get(
                        "/api/v1/analytics/hotspots",
                        params={"lat": lat, "lng": lng, "radius_km": 5},
                    ),
                    samples,
                    warmup,
                ),
                await _measure(
                    "accidents_region",
                    lambda: client.get(
                        "/api/v1/accidents",
                        params={"region_id": region_id, "page": 1, "per_page": 25, "sort": "date"},
                    ),
                    samples,
                    warmup,
                ),
                await _measure(
                    "route_risk_10km",
                    lambda: client.post("/api/v1/analytics/route-risk", json=route_payload),
                    samples,
                    warmup,
                ),
            ]
    finally:
        engine.sync_engine.echo = previous_echo


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 9 performance benchmark runner.")
    parser.add_argument("--samples", type=int, default=30, help="Measured requests per endpoint.")
    parser.add_argument("--warmup", type=int, default=5, help="Warm-up requests per endpoint.")
    parser.add_argument(
        "--output-json",
        default="docs/phase9-benchmark-results.json",
        help="Path to write benchmark results JSON.",
    )
    parser.add_argument(
        "--dataset-label",
        default="Local full import (2019-2023)",
        help="Dataset label included in output metadata.",
    )
    parser.add_argument(
        "--verbose-sql",
        action="store_true",
        help="Show SQLAlchemy engine logs during benchmark execution.",
    )
    args = parser.parse_args()
    if args.samples < 1:
        raise ValueError("--samples must be >= 1")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0")
    if not args.verbose_sql:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

    summaries = asyncio.run(_run_benchmark(args.samples, args.warmup, args.verbose_sql))

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "protocol": {
            "dataset": args.dataset_label,
            "database": "Local Docker PostgreSQL",
            "concurrency": 1,
            "client": "httpx.AsyncClient + ASGITransport (in-process HTTP)",
            "samples": args.samples,
            "warmup": args.warmup,
        },
        "results": [asdict(summary) for summary in summaries],
    }
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    print(f"Wrote benchmark JSON to {args.output_json}")
    print()
    print("Endpoint               p50(ms)  p95(ms)  target(ms)  pass")
    for summary in summaries:
        status = "yes" if summary.pass_target else "no"
        print(
            f"{summary.name:<21} {summary.p50_ms:>7.2f}  {summary.p95_ms:>7.2f}  "
            f"{summary.target_ms:>10.2f}  {status}"
        )


if __name__ == "__main__":
    main()

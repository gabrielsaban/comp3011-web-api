from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache

import_module = importlib.import_module("scripts.import")
_resolve_lad_lookup = import_module._resolve_lad_lookup
_truncate_for_full_refresh = import_module._truncate_for_full_refresh
enrich_accidents_with_midas = import_module.enrich_accidents_with_midas
import_midas = import_module.import_midas
import_stats19 = import_module.import_stats19
recompute_dbscan_clusters = import_module.recompute_dbscan_clusters


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def _write_badc(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_stats19_fixture(root: Path) -> Any:
    collisions = root / "dft-road-casualty-statistics-collision-1979-latest-published-year.csv"
    vehicles = root / "dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv"
    casualties = root / "dft-road-casualty-statistics-casualty-1979-latest-published-year.csv"

    collision_header = (
        "collision_index,collision_year,date,time,day_of_week,latitude,longitude,"
        "local_authority_ons_district,local_authority_district,collision_severity,"
        "road_type,junction_detail,light_conditions,weather_conditions,"
        "road_surface_conditions,speed_limit,urban_or_rural_area,"
        "did_police_officer_attend_scene_of_accident,number_of_vehicles,number_of_casualties"
    )
    collision_rows: list[str] = []
    for i in range(10):
        collision_id = f"2023TEST{i:04d}"
        severity = 1 if i < 2 else 2 if i < 5 else 3
        minute = i * 3
        collision_rows.append(
            f"{collision_id},2023,01/06/2023,08:{minute:02d},5,51.5100,-0.0900,"
            f"E09000001,City of London,{severity},6,3,1,1,1,30,1,1,1,1"
        )
    _write_csv(collisions, collision_header, collision_rows)

    vehicle_header = (
        "collision_index,collision_year,vehicle_reference,vehicle_type,age_of_driver,"
        "sex_of_driver,engine_capacity_cc,propulsion_code,age_of_vehicle,journey_purpose_of_driver"
    )
    vehicle_rows = [f"2023TEST{i:04d},2023,1,9,30,1,1600,1,4,1" for i in range(10)]
    _write_csv(vehicles, vehicle_header, vehicle_rows)

    casualty_header = (
        "collision_index,collision_year,casualty_reference,casualty_severity,"
        "vehicle_reference,casualty_class,casualty_type,sex_of_casualty,age_of_casualty"
    )
    casualty_rows = [
        f"2023TEST{i:04d},2023,1,{1 if i < 2 else 2 if i < 5 else 3},1,1,1,1,30" for i in range(10)
    ]
    _write_csv(casualties, casualty_header, casualty_rows)

    return import_module.Stats19Files(
        collisions=collisions,
        vehicles=vehicles,
        casualties=casualties,
    )


def _build_lad_fixture(path: Path) -> Path:
    _write_csv(
        path,
        "LAD23CD,LAD23NM,ITL121NM",
        ["E09000001,City of London,London"],
    )
    return path


def _build_midas_fixture(weather_root: Path, rain_root: Path) -> None:
    station_dir = weather_root / "london" / "00001_test-station"
    rain_station_dir = rain_root / "london" / "00001_test-station"
    capability_lines = [
        "Conventions,G,BADC-CSV,1",
        "observation_station,G,test-station",
        "src_id,G,00001",
        'location,G,"51.5100,-0.0900"',
        "height,G,15,m",
        'date_valid,G,"2019-01-01 00:00:00,2024-12-31 23:59:59"',
        "data",
        "id,id_type,met_domain_name,first_year,last_year",
        "1,DCNN,DLY3208,2019,2024",
        "end data",
    ]
    _write_badc(
        station_dir
        / "midas-open_uk-hourly-weather-obs_dv-202507_london_00001_test-station_capability.csv",
        capability_lines,
    )
    _write_badc(
        rain_station_dir
        / "midas-open_uk-hourly-rain-obs_dv-202507_london_00001_test-station_capability.csv",
        capability_lines,
    )

    weather_lines = [
        "Conventions,G,BADC-CSV,1",
        "data",
        "ob_time,src_id,air_temperature,air_temperature_q,visibility,visibility_q,wind_speed,wind_speed_q,wind_speed_unit_id",  # noqa: E501
        "2023-06-01 08:00:00,1,12.5,0,600,0,5.0,0,1",
        "2023-06-01 09:00:00,1,13.0,0,650,0,5.5,0,1",
        "end data",
    ]
    _write_badc(
        station_dir
        / "qc-version-1"
        / "midas-open_uk-hourly-weather-obs_dv-202507_london_00001_test-station_qcv-1_2023.csv",
        weather_lines,
    )

    rain_lines = [
        "Conventions,G,BADC-CSV,1",
        "data",
        "met_domain_name,ob_hour_count,prcp_amt_q,ob_end_time,src_id,prcp_amt",
        "AWSHRLY,1,0,2023-06-01 08:00:00,1,0.6",
        "end data",
    ]
    _write_badc(
        rain_station_dir
        / "qc-version-1"
        / "midas-open_uk-hourly-rain-obs_dv-202507_london_00001_test-station_qcv-1_2023.csv",
        rain_lines,
    )


async def _snapshot(session: AsyncSession) -> dict[str, object]:
    scalar_queries = {
        "accident_count": "SELECT COUNT(*) FROM accident",
        "vehicle_count": "SELECT COUNT(*) FROM vehicle",
        "casualty_count": "SELECT COUNT(*) FROM casualty",
        "station_count": "SELECT COUNT(*) FROM weather_station",
        "observation_count": "SELECT COUNT(*) FROM weather_observation",
        "cluster_count": "SELECT COUNT(*) FROM cluster",
        "weather_links": "SELECT COUNT(*) FROM accident WHERE weather_observation_id IS NOT NULL",
        "cluster_links": "SELECT COUNT(*) FROM accident WHERE cluster_id IS NOT NULL",
    }
    snapshot: dict[str, object] = {}
    for key, sql in scalar_queries.items():
        result = await session.execute(text(sql))
        snapshot[key] = int(result.scalar() or 0)

    cluster_totals = await session.execute(
        text(
            "SELECT COALESCE(SUM(accident_count), 0), COALESCE(SUM(fatal_count), 0), "
            "COALESCE(SUM(serious_count), 0) FROM cluster"
        )
    )
    row = cluster_totals.one()
    snapshot["cluster_totals"] = (int(row[0]), int(row[1]), int(row[2]))
    snapshot["speed_rates"] = sorted(cache.SPEED_FATAL_RATES.items())
    snapshot["heatmap_total"] = sum(
        sum(hour_counts.values()) for hour_counts in cache.HEATMAP.values()
    )
    snapshot["p99_density"] = round(cache.P99_DENSITY, 6)
    return snapshot


@pytest.mark.asyncio
async def test_phase7_pipeline_rerun_is_deterministic(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    stats_root = tmp_path / "stats19"
    lad_path = tmp_path / "lad" / "lookup.csv"
    weather_root = tmp_path / "midas" / "hourly-weather"
    rain_root = tmp_path / "midas" / "hourly-rain"

    stats_files = _build_stats19_fixture(stats_root)
    lad_lookup = _build_lad_fixture(lad_path)
    _build_midas_fixture(weather_root, rain_root)

    snapshots: list[dict[str, object]] = []
    for _ in range(2):
        await _truncate_for_full_refresh(db_session)
        await import_stats19(
            session=db_session,
            files=stats_files,
            lad_path=_resolve_lad_lookup(lad_lookup),
            year_from=2023,
            year_to=2023,
        )
        await import_midas(
            session=db_session,
            weather_root=weather_root,
            rain_root=rain_root,
            year_from=2023,
            year_to=2023,
        )
        await enrich_accidents_with_midas(db_session)
        await recompute_dbscan_clusters(db_session)
        await cache.build_startup_caches(db_session)
        await db_session.commit()
        snapshots.append(await _snapshot(db_session))

    first, second = snapshots
    assert first == second
    assert first["accident_count"] == 10
    assert first["weather_links"] == 10
    assert first["cluster_count"] == 1
    assert first["cluster_links"] == 10
    assert first["cluster_totals"] == (10, 2, 3)

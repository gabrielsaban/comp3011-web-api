from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import derive_age_band
from app.core.badc_csv import file_looks_like_html, iter_badc_data_rows, parse_badc_metadata
from app.core.import_normalization import (
    is_usable_q_flag,
    normalize_casualty_vehicle_ref,
    normalize_negative_one_unknown,
    normalize_nullable_code,
    normalize_police_attended,
    normalize_region_name,
    normalize_speed_limit,
    normalize_urban_or_rural,
    normalize_visibility_m,
    normalize_wind_speed_ms,
    parse_float,
    parse_int,
    parse_iso_datetime,
    parse_stats19_date,
    parse_stats19_time,
)
from app.database import AsyncSessionLocal
from app.models import (
    Accident,
    Casualty,
    JunctionDetail,
    LightCondition,
    LocalAuthority,
    Region,
    RoadSurface,
    RoadType,
    Severity,
    Vehicle,
    VehicleType,
    WeatherCondition,
    WeatherObservation,
    WeatherStation,
)

COLLISION_GLOB = "*collision*.csv"
VEHICLE_GLOB = "*vehicle*.csv"
CASUALTY_GLOB = "*casualty*.csv"
LAD_GLOB = "*Local_Authority_District*Lookup*.csv"
QCV_YEAR_RE = re.compile(r"_qcv-1_(\d{4})\.csv$")

CHUNK_SIZE = 5000


@dataclass
class ImportPaths:
    stats19_root: Path
    lad_lookup_csv: Path
    midas_weather_root: Path
    midas_rain_root: Path


@dataclass
class Stats19Files:
    collisions: Path
    vehicles: Path
    casualties: Path


@dataclass
class LookupCodeSets:
    severity: set[int]
    road_type: set[int]
    junction_detail: set[int]
    light_condition: set[int]
    weather_condition: set[int]
    road_surface: set[int]
    vehicle_type: set[int]


@dataclass
class LadRecord:
    code: str
    name: str
    region_name: str


@dataclass
class StationMeta:
    station_id: int
    name: str
    latitude: float
    longitude: float
    elevation_m: int | None
    active_from: date | None
    active_to: date | None


@dataclass
class ObservationRow:
    temperature_c: float | None = None
    precipitation_mm: float | None = None
    wind_speed_ms: float | None = None
    visibility_m: int | None = None


SEVERITY_LABELS = {
    1: "Fatal",
    2: "Serious",
    3: "Slight",
}

ROAD_TYPE_LABELS = {
    1: "Roundabout",
    2: "One way street",
    3: "Dual carriageway",
    6: "Single carriageway",
    7: "Slip road",
    9: "Unknown",
    12: "One way street/slip road",
}

JUNCTION_DETAIL_LABELS = {
    0: "Not at junction or within 20 metres",
    1: "Roundabout",
    2: "Mini-roundabout",
    3: "T or staggered junction",
    5: "Slip road",
    6: "Crossroads",
    7: "More than 4 arms",
    8: "Private drive or entrance",
    9: "Other junction",
}

LIGHT_CONDITION_LABELS = {
    1: "Daylight",
    4: "Darkness - lights lit",
    5: "Darkness - lights unlit",
    6: "Darkness - no lighting",
    7: "Darkness - lighting unknown",
}

WEATHER_CONDITION_LABELS = {
    1: "Fine no high winds",
    2: "Raining no high winds",
    3: "Snowing no high winds",
    4: "Fine + high winds",
    5: "Raining + high winds",
    6: "Snowing + high winds",
    7: "Fog or mist",
    8: "Other",
    9: "Unknown",
}

ROAD_SURFACE_LABELS = {
    1: "Dry",
    2: "Wet or damp",
    3: "Snow",
    4: "Frost or ice",
    5: "Flood over 3cm deep",
    6: "Oil or diesel",
    7: "Mud",
}

VEHICLE_TYPE_LABELS = {
    1: "Pedal cycle",
    2: "Motorcycle 50cc and under",
    3: "Motorcycle 125cc and under",
    4: "Motorcycle over 125cc and up to 500cc",
    5: "Motorcycle over 500cc",
    8: "Taxi/private hire car",
    9: "Car",
    10: "Minibus",
    11: "Bus or coach",
    16: "Ridden horse",
    17: "Agricultural vehicle",
    18: "Tram",
    19: "Van/Goods 3.5 tonnes mgw or under",
    20: "Goods over 3.5t and under 7.5t",
    21: "Goods over 7.5t",
    22: "Mobility scooter",
    23: "Electric motorcycle",
    90: "Other vehicle",
    97: "Motorcycle - unknown cc",
    98: "Goods vehicle - unknown weight",
    99: "Unknown vehicle type",
}

CASUALTY_CLASS_LABELS = {
    1: "Driver",
    2: "Passenger",
    3: "Pedestrian",
}

SEX_LABELS = {
    1: "Male",
    2: "Female",
}


def _label_for_code(code: int, labels: dict[int, str], prefix: str) -> str:
    return labels.get(code, f"{prefix} ({code})")


def _resolve_stats19_files(root: Path) -> Stats19Files:
    collisions = next(root.glob(COLLISION_GLOB), None)
    vehicles = next(root.glob(VEHICLE_GLOB), None)
    casualties = next(root.glob(CASUALTY_GLOB), None)

    missing = [
        name
        for name, value in {
            "collisions": collisions,
            "vehicles": vehicles,
            "casualties": casualties,
        }.items()
        if value is None
    ]
    if missing:
        raise FileNotFoundError(f"Missing STATS19 files in {root}: {', '.join(missing)}")

    return Stats19Files(
        collisions=collisions,  # type: ignore[arg-type]
        vehicles=vehicles,  # type: ignore[arg-type]
        casualties=casualties,  # type: ignore[arg-type]
    )


def _resolve_lad_lookup(path_or_dir: Path) -> Path:
    if path_or_dir.is_file():
        return path_or_dir
    candidate = next(path_or_dir.glob(LAD_GLOB), None)
    if candidate is None:
        raise FileNotFoundError(f"No LAD lookup file found in {path_or_dir}")
    return candidate


def _iter_stats19_rows(path: Path, year_from: int, year_to: int) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            year = parse_int(row.get("collision_year"))
            if year is None:
                continue
            if year_from <= year <= year_to:
                yield row


def _scan_lookup_codes(files: Stats19Files, year_from: int, year_to: int) -> LookupCodeSets:
    severity_codes: set[int] = set()
    road_types: set[int] = set()
    junctions: set[int] = set()
    lights: set[int] = set()
    weather: set[int] = set()
    surfaces: set[int] = set()
    vehicle_types: set[int] = set()

    for row in _iter_stats19_rows(files.collisions, year_from, year_to):
        sev = parse_int(row.get("collision_severity"))
        if sev is not None:
            severity_codes.add(sev)

        maybe_code = normalize_nullable_code(row.get("road_type"))
        if maybe_code is not None:
            road_types.add(maybe_code)

        maybe_code = normalize_nullable_code(row.get("junction_detail"))
        if maybe_code is not None:
            junctions.add(maybe_code)

        maybe_code = normalize_nullable_code(row.get("light_conditions"))
        if maybe_code is not None:
            lights.add(maybe_code)

        maybe_code = normalize_nullable_code(row.get("weather_conditions"))
        if maybe_code is not None:
            weather.add(maybe_code)

        maybe_code = normalize_nullable_code(row.get("road_surface_conditions"))
        if maybe_code is not None:
            surfaces.add(maybe_code)

    for row in _iter_stats19_rows(files.vehicles, year_from, year_to):
        maybe_code = normalize_nullable_code(row.get("vehicle_type"))
        if maybe_code is not None:
            vehicle_types.add(maybe_code)

    for row in _iter_stats19_rows(files.casualties, year_from, year_to):
        sev = parse_int(row.get("casualty_severity"))
        if sev is not None:
            severity_codes.add(sev)

    return LookupCodeSets(
        severity=severity_codes,
        road_type=road_types,
        junction_detail=junctions,
        light_condition=lights,
        weather_condition=weather,
        road_surface=surfaces,
        vehicle_type=vehicle_types,
    )


def _load_lad_records(path: Path) -> dict[str, LadRecord]:
    records: dict[str, LadRecord] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = (row.get("LAD23CD") or "").strip()
            if not code or code in records:
                continue
            name = (row.get("LAD23NM") or "").strip()
            region = normalize_region_name((row.get("ITL121NM") or "Unknown").strip())
            records[code] = LadRecord(code=code, name=name, region_name=region)
    return records


async def _load_lookup_tables(session: AsyncSession, codes: LookupCodeSets) -> None:
    severity_rows = [
        {"id": code, "label": _label_for_code(code, SEVERITY_LABELS, "Severity")}
        for code in sorted(codes.severity)
    ]
    road_type_rows = [
        {"id": code, "label": _label_for_code(code, ROAD_TYPE_LABELS, "Road type")}
        for code in sorted(codes.road_type)
    ]
    junction_rows = [
        {"id": code, "label": _label_for_code(code, JUNCTION_DETAIL_LABELS, "Junction")}
        for code in sorted(codes.junction_detail)
    ]
    light_rows = [
        {"id": code, "label": _label_for_code(code, LIGHT_CONDITION_LABELS, "Light condition")}
        for code in sorted(codes.light_condition)
    ]
    weather_rows = [
        {"id": code, "label": _label_for_code(code, WEATHER_CONDITION_LABELS, "Weather condition")}
        for code in sorted(codes.weather_condition)
    ]
    road_surface_rows = [
        {"id": code, "label": _label_for_code(code, ROAD_SURFACE_LABELS, "Road surface")}
        for code in sorted(codes.road_surface)
    ]
    vehicle_rows = [
        {"id": code, "label": _label_for_code(code, VEHICLE_TYPE_LABELS, "Vehicle type")}
        for code in sorted(codes.vehicle_type)
    ]

    if severity_rows:
        await session.execute(insert(Severity), severity_rows)
    if road_type_rows:
        await session.execute(insert(RoadType), road_type_rows)
    if junction_rows:
        await session.execute(insert(JunctionDetail), junction_rows)
    if light_rows:
        await session.execute(insert(LightCondition), light_rows)
    if weather_rows:
        await session.execute(insert(WeatherCondition), weather_rows)
    if road_surface_rows:
        await session.execute(insert(RoadSurface), road_surface_rows)
    if vehicle_rows:
        await session.execute(insert(VehicleType), vehicle_rows)


def _collect_local_authority_inputs(
    collisions_path: Path, year_from: int, year_to: int
) -> dict[str, str]:
    code_to_name: dict[str, str] = {}
    for row in _iter_stats19_rows(collisions_path, year_from, year_to):
        code = (row.get("local_authority_ons_district") or "").strip()
        name = (row.get("local_authority_district") or "").strip()
        if code and code not in code_to_name:
            code_to_name[code] = name
    return code_to_name


async def _load_regions_and_local_authorities(
    session: AsyncSession,
    lad_by_code: dict[str, LadRecord],
    collision_la_fallback_names: dict[str, str],
) -> dict[str, int]:
    region_names: set[str] = set()
    deduped_la_rows: dict[tuple[str, str], tuple[str, str]] = {}

    for code, fallback_name in collision_la_fallback_names.items():
        lookup = lad_by_code.get(code)
        if lookup is None:
            la_name = fallback_name or f"Unknown LA ({code})"
            region_name = "Unknown"
        else:
            la_name = lookup.name
            region_name = lookup.region_name

        region_names.add(region_name)
        deduped_la_rows[(la_name, region_name)] = (code, la_name)

    await session.execute(insert(Region), [{"name": name} for name in sorted(region_names)])
    await session.flush()

    region_rows = await session.execute(text('SELECT id, name FROM "region"'))
    region_id_by_name = {name: region_id for region_id, name in region_rows}

    la_insert_rows = [
        {"name": la_name, "region_id": region_id_by_name[region_name]}
        for (la_name, region_name) in sorted(deduped_la_rows.keys())
    ]
    await session.execute(insert(LocalAuthority), la_insert_rows)
    await session.flush()

    la_rows = await session.execute(text('SELECT id, name, region_id FROM "local_authority"'))
    la_id_by_key = {(name, region_id): la_id for la_id, name, region_id in la_rows}

    code_to_la_id: dict[str, int] = {}
    for code, fallback_name in collision_la_fallback_names.items():
        lookup = lad_by_code.get(code)
        if lookup is None:
            la_name = fallback_name or f"Unknown LA ({code})"
            region_name = "Unknown"
        else:
            la_name = lookup.name
            region_name = lookup.region_name

        region_id = region_id_by_name[region_name]
        code_to_la_id[code] = la_id_by_key[(la_name, region_id)]

    return code_to_la_id


async def _truncate_for_full_refresh(session: AsyncSession) -> None:
    await session.execute(
        text("UPDATE accident SET weather_observation_id = NULL, cluster_id = NULL")
    )
    await session.execute(text("TRUNCATE vehicle, casualty, accident RESTART IDENTITY CASCADE"))
    await session.execute(
        text("TRUNCATE weather_observation, weather_station RESTART IDENTITY CASCADE")
    )
    await session.execute(text("TRUNCATE cluster RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE local_authority, region RESTART IDENTITY CASCADE"))

    # Lookup tables are static reference data and are kept across runs.
    await session.execute(
        text(
            "DELETE FROM severity; DELETE FROM road_type; DELETE FROM junction_detail; "
            "DELETE FROM light_condition; DELETE FROM weather_condition; "
            "DELETE FROM road_surface; DELETE FROM vehicle_type;"
        )
    )


async def _truncate_for_stats19_reload(session: AsyncSession) -> None:
    await session.execute(
        text("UPDATE accident SET weather_observation_id = NULL, cluster_id = NULL")
    )
    await session.execute(text("TRUNCATE vehicle, casualty, accident RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE cluster RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE local_authority, region RESTART IDENTITY CASCADE"))
    await session.execute(
        text(
            "DELETE FROM severity; DELETE FROM road_type; DELETE FROM junction_detail; "
            "DELETE FROM light_condition; DELETE FROM weather_condition; "
            "DELETE FROM road_surface; DELETE FROM vehicle_type;"
        )
    )


async def _truncate_for_midas_reload(session: AsyncSession) -> None:
    await session.execute(text("UPDATE accident SET weather_observation_id = NULL"))
    await session.execute(
        text("TRUNCATE weather_observation, weather_station RESTART IDENTITY CASCADE")
    )


def _iter_chunks(
    rows: Iterator[dict[str, Any]], size: int = CHUNK_SIZE
) -> Iterator[list[dict[str, Any]]]:
    chunk: list[dict[str, Any]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _build_accident_rows(
    collisions_path: Path,
    year_from: int,
    year_to: int,
    local_authority_id_by_code: dict[str, int],
) -> Iterator[dict[str, Any]]:
    for row in _iter_stats19_rows(collisions_path, year_from, year_to):
        accident_id = (row.get("collision_index") or "").strip()
        accident_date = parse_stats19_date(row.get("date"))
        if not accident_id or accident_date is None:
            continue

        severity_id = parse_int(row.get("collision_severity"))
        if severity_id is None:
            continue

        local_authority_code = (row.get("local_authority_ons_district") or "").strip()
        local_authority_id = local_authority_id_by_code.get(local_authority_code)

        yield {
            "id": accident_id,
            "date": accident_date,
            "time": parse_stats19_time(row.get("time")),
            "day_of_week": parse_int(row.get("day_of_week")),
            "latitude": parse_float(row.get("latitude")),
            "longitude": parse_float(row.get("longitude")),
            "local_authority_id": local_authority_id,
            "severity_id": severity_id,
            "road_type_id": normalize_nullable_code(row.get("road_type")),
            "junction_detail_id": normalize_nullable_code(row.get("junction_detail")),
            "light_condition_id": normalize_nullable_code(row.get("light_conditions")),
            "weather_condition_id": normalize_nullable_code(row.get("weather_conditions")),
            "road_surface_id": normalize_nullable_code(row.get("road_surface_conditions")),
            "speed_limit": normalize_speed_limit(row.get("speed_limit")),
            "urban_or_rural": normalize_urban_or_rural(row.get("urban_or_rural_area")),
            "police_attended": normalize_police_attended(
                row.get("did_police_officer_attend_scene_of_accident")
            ),
            "number_of_vehicles": parse_int(row.get("number_of_vehicles")) or 0,
            "number_of_casualties": parse_int(row.get("number_of_casualties")) or 0,
            "weather_observation_id": None,
            "cluster_id": None,
        }


def _build_vehicle_rows(
    vehicles_path: Path, year_from: int, year_to: int
) -> Iterator[dict[str, Any]]:
    for row in _iter_stats19_rows(vehicles_path, year_from, year_to):
        accident_id = (row.get("collision_index") or "").strip()
        vehicle_ref = parse_int(row.get("vehicle_reference"))
        if not accident_id or vehicle_ref is None:
            continue

        sex_of_driver_code = parse_int(row.get("sex_of_driver"))
        yield {
            "accident_id": accident_id,
            "vehicle_ref": vehicle_ref,
            "vehicle_type_id": normalize_nullable_code(row.get("vehicle_type")),
            "age_of_driver": normalize_negative_one_unknown(row.get("age_of_driver")),
            "sex_of_driver": SEX_LABELS.get(sex_of_driver_code)
            if sex_of_driver_code is not None
            else None,
            "engine_capacity_cc": normalize_negative_one_unknown(row.get("engine_capacity_cc")),
            "propulsion_code": (row.get("propulsion_code") or "").strip() or None,
            "age_of_vehicle": normalize_negative_one_unknown(row.get("age_of_vehicle")),
            "journey_purpose": (row.get("journey_purpose_of_driver") or "").strip() or None,
        }


def _build_casualty_rows(
    casualties_path: Path, year_from: int, year_to: int
) -> Iterator[dict[str, Any]]:
    for row in _iter_stats19_rows(casualties_path, year_from, year_to):
        accident_id = (row.get("collision_index") or "").strip()
        casualty_ref = parse_int(row.get("casualty_reference"))
        severity_id = parse_int(row.get("casualty_severity"))
        if not accident_id or casualty_ref is None or severity_id is None:
            continue

        age = normalize_negative_one_unknown(row.get("age_of_casualty"))
        casualty_class_code = parse_int(row.get("casualty_class"))
        sex_code = parse_int(row.get("sex_of_casualty"))
        casualty_class = (
            CASUALTY_CLASS_LABELS.get(casualty_class_code)
            if casualty_class_code is not None
            else None
        )
        sex = SEX_LABELS.get(sex_code) if sex_code is not None else None

        casualty_type_code = normalize_negative_one_unknown(row.get("casualty_type"))
        casualty_type = str(casualty_type_code) if casualty_type_code is not None else None

        yield {
            "accident_id": accident_id,
            "vehicle_ref": normalize_casualty_vehicle_ref(row.get("vehicle_reference")),
            "casualty_ref": casualty_ref,
            "severity_id": severity_id,
            "casualty_class": casualty_class,
            "casualty_type": casualty_type,
            "sex": sex,
            "age": age,
            "age_band": derive_age_band(age),
        }


def _station_key_and_year(path: Path) -> tuple[str, int] | None:
    match = QCV_YEAR_RE.search(path.name)
    if match is None:
        return None
    year = int(match.group(1))
    # .../<county>/<station>/qc-version-1/<file.csv>
    station_key = path.parents[1].name
    return station_key, year


def _iter_qcv_files(root: Path, year_from: int, year_to: int) -> Iterator[Path]:
    for path in root.rglob("*_qcv-1_*.csv"):
        year_match = QCV_YEAR_RE.search(path.name)
        if year_match is None:
            continue
        year = int(year_match.group(1))
        if year_from <= year <= year_to:
            yield path


def _collect_station_metadata(paths: list[Path]) -> dict[int, StationMeta]:
    station_by_id: dict[int, StationMeta] = {}

    for capability_file in paths:
        metadata = parse_badc_metadata(capability_file)

        src_id_raw = (metadata.get("src_id") or [""])[0]
        station_id = parse_int(src_id_raw)
        station_name = (metadata.get("observation_station") or [""])[0].strip()
        location = (metadata.get("location") or [""])[0]
        height_raw = (metadata.get("height") or [""])[0]
        elevation_m = parse_int(height_raw)
        date_valid = (metadata.get("date_valid") or [""])[0]

        if station_id is None:
            continue
        if "," not in location:
            continue

        lat_raw, lon_raw = [token.strip() for token in location.split(",", maxsplit=1)]
        latitude = parse_float(lat_raw)
        longitude = parse_float(lon_raw)
        if latitude is None or longitude is None:
            continue

        active_from = None
        active_to = None
        if "," in date_valid:
            start_raw, end_raw = [token.strip() for token in date_valid.split(",", maxsplit=1)]
            start_dt = parse_iso_datetime(start_raw)
            end_dt = parse_iso_datetime(end_raw)
            active_from = start_dt.date() if start_dt is not None else None
            active_to = end_dt.date() if end_dt is not None else None

        current = station_by_id.get(station_id)
        if current is None:
            station_by_id[station_id] = StationMeta(
                station_id=station_id,
                name=station_name or f"station-{station_id}",
                latitude=latitude,
                longitude=longitude,
                elevation_m=elevation_m,
                active_from=active_from,
                active_to=active_to,
            )
            continue

        if current.active_from is None or (
            active_from is not None and active_from < current.active_from
        ):
            current.active_from = active_from
        if current.active_to is None or (active_to is not None and active_to > current.active_to):
            current.active_to = active_to
        if current.elevation_m is None and elevation_m is not None:
            current.elevation_m = elevation_m

    return station_by_id


def _parse_weather_qcv_file(path: Path) -> tuple[int | None, dict[Any, ObservationRow]]:
    rows_by_time: dict[Any, ObservationRow] = {}
    station_id: int | None = None

    for row in iter_badc_data_rows(path):
        observed_at = parse_iso_datetime(row.get("ob_time"))
        station_code = parse_int(row.get("src_id"))
        if observed_at is None or station_code is None:
            continue

        station_id = station_code

        temperature = None
        if is_usable_q_flag(row.get("air_temperature_q")):
            temperature = parse_float(row.get("air_temperature"))

        visibility = None
        if is_usable_q_flag(row.get("visibility_q")):
            visibility = normalize_visibility_m(row.get("visibility"))

        wind = None
        if is_usable_q_flag(row.get("wind_speed_q")):
            wind = normalize_wind_speed_ms(row.get("wind_speed"), row.get("wind_speed_unit_id"))

        if temperature is None and visibility is None and wind is None:
            continue

        item = rows_by_time.setdefault(observed_at, ObservationRow())
        if temperature is not None:
            item.temperature_c = temperature
        if visibility is not None:
            item.visibility_m = visibility
        if wind is not None:
            item.wind_speed_ms = wind

    return station_id, rows_by_time


def _parse_rain_qcv_file(path: Path) -> tuple[int | None, dict[Any, ObservationRow]]:
    rows_by_time: dict[Any, ObservationRow] = {}
    station_id: int | None = None

    for row in iter_badc_data_rows(path):
        if (row.get("met_domain_name") or "").strip() != "AWSHRLY":
            continue
        if parse_int(row.get("ob_hour_count")) != 1:
            continue
        if not is_usable_q_flag(row.get("prcp_amt_q")):
            continue

        observed_at = parse_iso_datetime(row.get("ob_end_time"))
        station_code = parse_int(row.get("src_id"))
        precipitation = parse_float(row.get("prcp_amt"))
        if observed_at is None or station_code is None or precipitation is None:
            continue

        station_id = station_code
        item = rows_by_time.setdefault(observed_at, ObservationRow())
        item.precipitation_mm = precipitation

    return station_id, rows_by_time


async def import_stats19(
    session: AsyncSession, files: Stats19Files, lad_path: Path, year_from: int, year_to: int
) -> None:
    lookup_codes = _scan_lookup_codes(files, year_from, year_to)
    await _load_lookup_tables(session, lookup_codes)

    lad_by_code = _load_lad_records(lad_path)
    la_fallback_names = _collect_local_authority_inputs(files.collisions, year_from, year_to)
    local_authority_id_by_code = await _load_regions_and_local_authorities(
        session=session,
        lad_by_code=lad_by_code,
        collision_la_fallback_names=la_fallback_names,
    )

    for chunk in _iter_chunks(
        _build_accident_rows(
            collisions_path=files.collisions,
            year_from=year_from,
            year_to=year_to,
            local_authority_id_by_code=local_authority_id_by_code,
        )
    ):
        await session.execute(insert(Accident), chunk)

    for chunk in _iter_chunks(_build_vehicle_rows(files.vehicles, year_from, year_to)):
        await session.execute(insert(Vehicle), chunk)

    for chunk in _iter_chunks(_build_casualty_rows(files.casualties, year_from, year_to)):
        await session.execute(insert(Casualty), chunk)


async def import_midas(
    session: AsyncSession, weather_root: Path, rain_root: Path, year_from: int, year_to: int
) -> None:
    capability_files = sorted(
        list(weather_root.rglob("*_capability.csv"))
        + list(rain_root.rglob("*_capability.csv"))
    )
    station_meta = _collect_station_metadata(capability_files)

    station_rows = [
        {
            "id": station.station_id,
            "name": station.name,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "elevation_m": station.elevation_m,
            "active_from": station.active_from,
            "active_to": station.active_to,
        }
        for station in sorted(station_meta.values(), key=lambda item: item.station_id)
    ]
    if station_rows:
        await session.execute(insert(WeatherStation), station_rows)

    weather_files = list(_iter_qcv_files(weather_root, year_from, year_to))
    rain_files = list(_iter_qcv_files(rain_root, year_from, year_to))
    rain_by_key = {
        key: path for path in rain_files if (key := _station_key_and_year(path)) is not None
    }
    used_rain_keys: set[tuple[str, int]] = set()

    observation_batch: list[dict[str, Any]] = []

    for weather_file in sorted(weather_files):
        weather_key = _station_key_and_year(weather_file)
        rain_file = rain_by_key.get(weather_key) if weather_key is not None else None
        if weather_key is not None and rain_file is not None:
            used_rain_keys.add(weather_key)

        weather_station_id, weather_rows = _parse_weather_qcv_file(weather_file)
        rain_station_id: int | None = None
        rain_rows: dict[Any, ObservationRow] = {}
        if rain_file is not None:
            rain_station_id, rain_rows = _parse_rain_qcv_file(rain_file)

        station_id = weather_station_id or rain_station_id
        if station_id is None:
            continue

        merged = weather_rows
        for observed_at, rain_row in rain_rows.items():
            target = merged.setdefault(observed_at, ObservationRow())
            if rain_row.precipitation_mm is not None:
                target.precipitation_mm = rain_row.precipitation_mm

        for observed_at, item in merged.items():
            observation_batch.append(
                {
                    "station_id": station_id,
                    "observed_at": observed_at,
                    "temperature_c": item.temperature_c,
                    "precipitation_mm": item.precipitation_mm,
                    "wind_speed_ms": item.wind_speed_ms,
                    "visibility_m": item.visibility_m,
                }
            )
            if len(observation_batch) >= CHUNK_SIZE:
                await session.execute(insert(WeatherObservation), observation_batch)
                observation_batch = []

    for key, rain_file in sorted(rain_by_key.items()):
        if key in used_rain_keys:
            continue
        station_id, rain_rows = _parse_rain_qcv_file(rain_file)
        if station_id is None:
            continue

        for observed_at, item in rain_rows.items():
            observation_batch.append(
                {
                    "station_id": station_id,
                    "observed_at": observed_at,
                    "temperature_c": None,
                    "precipitation_mm": item.precipitation_mm,
                    "wind_speed_ms": None,
                    "visibility_m": None,
                }
            )
            if len(observation_batch) >= CHUNK_SIZE:
                await session.execute(insert(WeatherObservation), observation_batch)
                observation_batch = []

    if observation_batch:
        await session.execute(insert(WeatherObservation), observation_batch)


def validate_midas_tree(root: Path, label: str) -> list[str]:
    errors: list[str] = []
    if not root.exists():
        errors.append(f"[{label}] path does not exist: {root}")
        return errors

    csv_files = list(root.rglob("*.csv"))
    if not csv_files:
        errors.append(f"[{label}] no CSV files found under: {root}")
        return errors

    html_files = [path for path in csv_files if file_looks_like_html(path)]
    if html_files:
        errors.append(
            f"[{label}] detected {len(html_files)} HTML-auth payload files under CSV paths. "
            "Re-download with valid CEDA auth."
        )
    return errors


def _default_paths_from_settings() -> ImportPaths:
    stats19_root = Path(settings.stats19_data_path)
    lad_lookup = Path(settings.lad_lookup_csv_path)
    weather_root = Path(settings.midas_hourly_weather_path)
    rain_root = Path(settings.midas_hourly_rain_path)
    return ImportPaths(
        stats19_root=stats19_root,
        lad_lookup_csv=lad_lookup,
        midas_weather_root=weather_root,
        midas_rain_root=rain_root,
    )


def _parse_args() -> argparse.Namespace:
    defaults = _default_paths_from_settings()

    parser = argparse.ArgumentParser(description="Phase 7 import pipeline runner")
    parser.add_argument(
        "--mode",
        choices=["validate", "stats19", "midas", "run"],
        default="run",
        help="Pipeline stage to execute",
    )
    parser.add_argument("--stats19-root", type=Path, default=defaults.stats19_root)
    parser.add_argument("--lad-lookup", type=Path, default=defaults.lad_lookup_csv)
    parser.add_argument("--midas-weather-root", type=Path, default=defaults.midas_weather_root)
    parser.add_argument("--midas-rain-root", type=Path, default=defaults.midas_rain_root)
    parser.add_argument("--year-from", type=int, default=settings.import_year_from)
    parser.add_argument("--year-to", type=int, default=settings.import_year_to)
    return parser.parse_args()


async def _run_pipeline(args: argparse.Namespace) -> None:
    paths = ImportPaths(
        stats19_root=args.stats19_root,
        lad_lookup_csv=args.lad_lookup,
        midas_weather_root=args.midas_weather_root,
        midas_rain_root=args.midas_rain_root,
    )
    stats19_files = _resolve_stats19_files(paths.stats19_root)
    lad_lookup = _resolve_lad_lookup(paths.lad_lookup_csv)

    if args.mode == "validate":
        errors: list[str] = []
        errors.extend(validate_midas_tree(paths.midas_weather_root, "hourly-weather"))
        errors.extend(validate_midas_tree(paths.midas_rain_root, "hourly-rain"))
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print("Source validation passed.")
        return

    async with AsyncSessionLocal() as session:
        if args.mode == "run":
            print("Running full-refresh teardown...")
            await _truncate_for_full_refresh(session)
            await session.commit()

            print("Importing STATS19...")
            await import_stats19(
                session=session,
                files=stats19_files,
                lad_path=lad_lookup,
                year_from=args.year_from,
                year_to=args.year_to,
            )
            await session.commit()

            print("Importing MIDAS stations/observations...")
            await import_midas(
                session=session,
                weather_root=paths.midas_weather_root,
                rain_root=paths.midas_rain_root,
                year_from=args.year_from,
                year_to=args.year_to,
            )
            await session.commit()
            print(
                "Import stage complete (raw load). "
                "Enrichment/DBSCAN/cache recompute are implemented in the next Phase 7 slice."
            )
            return

        if args.mode == "stats19":
            print("Running stats19-only teardown...")
            await _truncate_for_stats19_reload(session)
            await session.commit()

            await import_stats19(
                session=session,
                files=stats19_files,
                lad_path=lad_lookup,
                year_from=args.year_from,
                year_to=args.year_to,
            )
            await session.commit()
            print("STATS19 import complete.")
            return

        if args.mode == "midas":
            print("Running midas-only teardown...")
            await _truncate_for_midas_reload(session)
            await session.commit()

            await import_midas(
                session=session,
                weather_root=paths.midas_weather_root,
                rain_root=paths.midas_rain_root,
                year_from=args.year_from,
                year_to=args.year_to,
            )
            await session.commit()
            print("MIDAS import complete.")


def main() -> None:
    args = _parse_args()
    import asyncio

    asyncio.run(_run_pipeline(args))


if __name__ == "__main__":
    main()

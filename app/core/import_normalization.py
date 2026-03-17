from __future__ import annotations

from datetime import date, datetime, time

UNKNOWN_INT_TOKENS = {"", "NA", "-1", "9", "99"}


def parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = raw.strip()
    if value in {"", "NA"}:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.strip()
    if value in {"", "NA"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_stats19_date(raw: str | None) -> date | None:
    if raw is None or raw.strip() == "":
        return None
    value = raw.strip()
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_stats19_time(raw: str | None) -> time | None:
    if raw is None or raw.strip() == "":
        return None
    value = raw.strip()
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def parse_iso_datetime(raw: str | None) -> datetime | None:
    if raw is None or raw.strip() in {"", "NA"}:
        return None
    value = raw.strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def normalize_speed_limit(raw: str | None) -> int | None:
    value = parse_int(raw)
    if value is None:
        return None
    if value in {99, -1}:
        return None
    return value


def normalize_urban_or_rural(raw: str | None) -> str | None:
    code = parse_int(raw)
    if code == 1:
        return "Urban"
    if code == 2:
        return "Rural"
    if code == 3:
        return "Unallocated"
    return None


def normalize_police_attended(raw: str | None) -> bool | None:
    code = parse_int(raw)
    if code == 1:
        return True
    if code == 2:
        return False
    return None


def normalize_nullable_code(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = raw.strip()
    if value in UNKNOWN_INT_TOKENS:
        return None
    return parse_int(value)


def normalize_casualty_vehicle_ref(raw: str | None) -> int | None:
    value = parse_int(raw)
    if value is None:
        return None
    if value == 0:
        return None
    return value


def normalize_region_name(raw: str) -> str:
    value = raw.strip()
    if value.endswith("(England)"):
        value = value.replace("(England)", "").strip()
    if value == "East":
        return "East of England"
    return value


def normalize_visibility_m(raw_decametres: str | None) -> int | None:
    value = parse_float(raw_decametres)
    if value is None:
        return None
    return int(round(value * 10))


def normalize_wind_speed_ms(raw_speed: str | None, raw_unit_id: str | None) -> float | None:
    speed = parse_float(raw_speed)
    if speed is None:
        return None

    unit = (raw_unit_id or "").strip()
    if unit in {"0", "1"}:
        return speed
    if unit in {"3", "4"}:
        return speed * 0.514444
    return speed


def is_usable_q_flag(raw: str | None) -> bool:
    if raw is None:
        return False
    value = raw.strip()
    if value in {"", "NA"}:
        return False
    # MIDAS open files commonly use 9 for missing/unavailable.
    return value != "9"

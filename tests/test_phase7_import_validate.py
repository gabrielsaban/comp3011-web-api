from __future__ import annotations

import importlib
from pathlib import Path

import_module = importlib.import_module("scripts.import")
Stats19Files = import_module.Stats19Files
validate_stats19_files = import_module.validate_stats19_files


def _write_csv(path: Path, header: str, rows: list[str] | None = None) -> None:
    lines = [header]
    if rows:
        lines.extend(rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_validate_stats19_files_accepts_expected_headers(tmp_path: Path) -> None:
    collisions = tmp_path / "collision.csv"
    vehicles = tmp_path / "vehicle.csv"
    casualties = tmp_path / "casualty.csv"

    _write_csv(
        collisions,
        "collision_index,collision_year,date,time,local_authority_ons_district,collision_severity",
        ["A1,2023,01/01/2023,09:00,E09000001,3"],
    )
    _write_csv(
        vehicles,
        "collision_index,collision_year,vehicle_reference,vehicle_type",
        ["A1,2023,1,9"],
    )
    _write_csv(
        casualties,
        "collision_index,collision_year,casualty_reference,casualty_severity",
        ["A1,2023,1,3"],
    )

    errors = validate_stats19_files(
        Stats19Files(collisions=collisions, vehicles=vehicles, casualties=casualties)
    )
    assert errors == []


def test_validate_stats19_files_flags_missing_columns_and_html(tmp_path: Path) -> None:
    collisions = tmp_path / "collision.csv"
    vehicles = tmp_path / "vehicle.csv"
    casualties = tmp_path / "casualty.csv"

    _write_csv(
        collisions,
        "collision_index,collision_year,date,time,collision_severity",
        ["A1,2023,01/01/2023,09:00,3"],
    )
    vehicles.write_text(
        "<!DOCTYPE html>\n<html><body>/account/signin</body></html>\n", encoding="utf-8"
    )
    _write_csv(
        casualties,
        "collision_index,collision_year,casualty_reference,casualty_severity",
        ["A1,2023,1,3"],
    )

    errors = validate_stats19_files(
        Stats19Files(collisions=collisions, vehicles=vehicles, casualties=casualties)
    )

    assert any("missing expected columns" in error for error in errors)
    assert any("appears to be HTML auth content" in error for error in errors)

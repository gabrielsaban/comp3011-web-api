from __future__ import annotations

from pathlib import Path

from app.core.badc_csv import (
    file_looks_like_html,
    is_badc_csv,
    iter_badc_data_rows,
    parse_badc_metadata,
)
from app.core.import_normalization import (
    is_usable_q_flag,
    normalize_casualty_vehicle_ref,
    normalize_nullable_code,
    normalize_police_attended,
    normalize_region_name,
    normalize_speed_limit,
    normalize_urban_or_rural,
    normalize_visibility_m,
    normalize_wind_speed_ms,
    parse_iso_datetime,
    parse_stats19_date,
    parse_stats19_time,
)


def test_stats19_date_and_time_parsing() -> None:
    assert parse_stats19_date("31/12/2023") is not None
    assert parse_stats19_date("2023-12-31") is None
    assert parse_stats19_time("09:41") is not None
    assert parse_stats19_time("9am") is None


def test_core_normalisation_rules() -> None:
    assert normalize_speed_limit("30") == 30
    assert normalize_speed_limit("99") is None
    assert normalize_speed_limit("-1") is None

    assert normalize_urban_or_rural("1") == "Urban"
    assert normalize_urban_or_rural("2") == "Rural"
    assert normalize_urban_or_rural("3") == "Unallocated"
    assert normalize_urban_or_rural("9") is None

    assert normalize_police_attended("1") is True
    assert normalize_police_attended("2") is False
    assert normalize_police_attended("3") is None

    assert normalize_nullable_code("9") is None
    assert normalize_nullable_code("-1") is None
    assert normalize_nullable_code("7") == 7

    assert normalize_casualty_vehicle_ref("0") is None
    assert normalize_casualty_vehicle_ref("2") == 2


def test_region_and_weather_value_normalisation() -> None:
    assert normalize_region_name("North West (England)") == "North West"
    assert normalize_region_name("East") == "East of England"
    assert normalize_region_name("Wales") == "Wales"

    assert normalize_visibility_m("40.0") == 400
    assert normalize_visibility_m("NA") is None

    assert normalize_wind_speed_ms("10.0", "1") == 10.0
    assert normalize_wind_speed_ms("10.0", "4") == 10.0 * 0.514444
    assert normalize_wind_speed_ms("NA", "1") is None

    assert is_usable_q_flag("6") is True
    assert is_usable_q_flag("9") is False
    assert is_usable_q_flag("NA") is False

    assert parse_iso_datetime("2023-01-01 09:00:00") is not None
    assert parse_iso_datetime("2023-01-01T09:00:00") is None


def test_badc_helpers_and_row_iteration(tmp_path: Path) -> None:
    badc_file = tmp_path / "sample.csv"
    badc_file.write_text(
        "Conventions,G,BADC-CSV,1\n"
        "observation_station,G,test-station\n"
        "src_id,G,00123\n"
        "location,G,53.8,-1.5\n"
        "data\n"
        "ob_time,src_id,air_temperature,air_temperature_q\n"
        "2023-01-01 09:00:00,123,4.5,6\n"
        "end data\n",
        encoding="utf-8",
    )

    html_file = tmp_path / "html.csv"
    html_file.write_text(
        '<!DOCTYPE html>\n<html>\n<form class="form-signin" action="/account/signin/">\n',
        encoding="utf-8",
    )

    assert is_badc_csv(badc_file) is True
    assert is_badc_csv(html_file) is False
    assert file_looks_like_html(html_file) is True
    assert file_looks_like_html(badc_file) is False

    metadata = parse_badc_metadata(badc_file)
    assert metadata["observation_station"][0] == "test-station"
    assert metadata["src_id"][0] == "00123"

    rows = list(iter_badc_data_rows(badc_file))
    assert len(rows) == 1
    assert rows[0]["ob_time"] == "2023-01-01 09:00:00"
    assert rows[0]["air_temperature"] == "4.5"

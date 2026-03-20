from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accident import Casualty
from tests.fixtures import seed_profile


async def test_accidents_by_time_returns_zero_filled_matrix(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/analytics/accidents-by-time")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 168

    cell_lookup = {(row["day_of_week"], row["hour"]): row for row in body["data"]}
    assert cell_lookup[(2, 8)]["accident_count"] == 1
    assert cell_lookup[(5, 17)]["accident_count"] == 2
    assert cell_lookup[(7, 2)]["accident_count"] == 1
    assert cell_lookup[(3, 0)]["accident_count"] == 0


async def test_accidents_by_time_filters_narrow_scope(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    all_rows = (await client.get("/api/v1/analytics/accidents-by-time")).json()["data"]
    assert sum(row["accident_count"] for row in all_rows) == 5

    one_day = await client.get(
        "/api/v1/analytics/accidents-by-time",
        params={"date_from": "2022-03-18", "date_to": "2022-03-18"},
    )
    assert one_day.status_code == 200
    assert sum(row["accident_count"] for row in one_day.json()["data"]) == 2

    empty_scope = await client.get("/api/v1/analytics/accidents-by-time", params={"region_id": 999})
    assert empty_scope.status_code == 200
    assert sum(row["accident_count"] for row in empty_scope.json()["data"]) == 0


async def test_annual_trend_returns_expected_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/analytics/annual-trend",
        params={"year_from": 2022, "year_to": 2022},
    )
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row == {
        "year": 2022,
        "accidents": 5,
        "casualties": 5,
        "fatal_casualties": 2,
        "change_pct": None,
    }


async def test_annual_trend_year_filter_can_return_empty(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/analytics/annual-trend",
        params={"year_from": 2021, "year_to": 2021},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_severity_by_conditions_weather_and_midas_dimension(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    weather = await client.get(
        "/api/v1/analytics/severity-by-conditions",
        params={"dimension": "weather"},
    )
    assert weather.status_code == 200
    weather_rows = {row["condition"]: row for row in weather.json()["data"]}
    assert weather_rows["Fine no high winds"]["total"] == 3
    assert weather_rows["Raining no high winds"]["total"] == 2
    assert weather.json()["query"]["coverage_pct"] == 100.0

    precipitation = await client.get(
        "/api/v1/analytics/severity-by-conditions",
        params={"dimension": "precipitation_band"},
    )
    assert precipitation.status_code == 200
    p_rows = {row["condition"]: row for row in precipitation.json()["data"]}
    assert p_rows["Dry (<0.2mm)"]["total"] == 2
    assert p_rows["Light (0.2-2mm)"]["total"] == 1
    assert precipitation.json()["query"]["coverage_pct"] == 60.0


@pytest.mark.parametrize(
    ("path", "params", "field_name"),
    [
        ("/api/v1/analytics/severity-by-conditions", {"dimension": "bad"}, "dimension"),
        ("/api/v1/analytics/severity-by-speed-limit", {"urban_or_rural": "Town"}, "urban_or_rural"),
        ("/api/v1/analytics/vulnerable-road-users", {"casualty_type": "Driver"}, "casualty_type"),
        ("/api/v1/analytics/weather-correlation", {"metric": "rainfall"}, "metric"),
        ("/api/v1/analytics/hotspots", {"lat": "999", "lng": "-1.5"}, "lat"),
    ],
)
async def test_analytics_query_validation_returns_422(
    client: AsyncClient,
    path: str,
    params: dict[str, str],
    field_name: str,
) -> None:
    response = await client.get(path, params=params)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["loc"][-1] == field_name for detail in body["error"]["details"])


async def test_severity_by_speed_limit_returns_expected_distribution(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get("/api/v1/analytics/severity-by-speed-limit")
    assert response.status_code == 200
    rows = {row["speed_limit"]: row for row in response.json()["data"]}
    assert rows[20]["total_accidents"] == 1
    assert rows[40]["total_accidents"] == 2
    assert rows[60]["fatal_rate_pct"] == 100.0


async def test_accidents_by_vehicle_type_and_journey_purpose(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    by_type = await client.get("/api/v1/analytics/accidents-by-vehicle-type")
    assert by_type.status_code == 200
    assert by_type.json()["data"] == [
        {
            "vehicle_type": "Car",
            "accidents_involved_in": 5,
            "fatal_count": 2,
            "serious_count": 2,
            "fatal_rate_pct": 40.0,
        }
    ]

    by_purpose = await client.get("/api/v1/analytics/severity-by-journey-purpose")
    assert by_purpose.status_code == 200
    assert by_purpose.json()["data"] == [
        {
            "journey_purpose": "Commute",
            "total_accidents": 5,
            "fatal": 2,
            "serious": 2,
            "slight": 1,
            "fatal_rate_pct": 40.0,
            "serious_or_fatal_rate_pct": 80.0,
        }
    ]


async def test_casualties_by_demographic_and_driver_age_severity(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    demographics = await client.get(
        "/api/v1/analytics/casualties-by-demographic",
        params={"severity": 1},
    )
    assert demographics.status_code == 200
    assert len(demographics.json()["data"]) == 2
    assert all(row["pct_of_total"] == 50.0 for row in demographics.json()["data"])

    driver_age = await client.get("/api/v1/analytics/driver-age-severity")
    assert driver_age.status_code == 200
    age_rows = {row["age_band"]: row for row in driver_age.json()["data"]}
    assert age_rows["25-34"]["total_accidents"] == 4
    assert age_rows["35-44"]["total_accidents"] == 1


async def test_fatal_condition_combinations_and_local_authority_ranking(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    combinations = await client.get(
        "/api/v1/analytics/fatal-condition-combinations",
        params={"year_from": 2022, "year_to": 2022, "min_count": 1, "limit": 2},
    )
    assert combinations.status_code == 200
    combo_rows = combinations.json()["data"]
    assert len(combo_rows) == 2
    assert combo_rows[0]["fatal_rate_pct"] == 100.0
    assert combo_rows[0]["fatal_rate_pct"] >= combo_rows[1]["fatal_rate_pct"]

    by_la = await client.get("/api/v1/analytics/accidents-by-local-authority")
    assert by_la.status_code == 200
    body = by_la.json()
    assert body["meta"]["total_authorities"] == 1
    assert body["data"][0]["local_authority"] == {
        "id": 14,
        "name": "Leeds",
        "region": "Yorkshire and The Humber",
    }
    assert body["data"][0]["total_accidents"] == 5

    by_la_empty_region = await client.get(
        "/api/v1/analytics/accidents-by-local-authority",
        params={"region_id": 999},
    )
    assert by_la_empty_region.status_code == 200
    assert by_la_empty_region.json()["meta"]["total_authorities"] == 0
    assert by_la_empty_region.json()["data"] == []


async def test_seasonal_pattern_police_profile_and_multi_vehicle(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    seasonal = await client.get(
        "/api/v1/analytics/seasonal-pattern",
        params={"year_from": 2022, "year_to": 2022},
    )
    assert seasonal.status_code == 200
    assert seasonal.json()["data"] == [
        {
            "month": 3,
            "month_label": "March",
            "total_accidents": 5,
            "fatal_accidents": 2,
            "fatal_rate_pct": 40.0,
            "avg_accidents_per_year": 5.0,
        }
    ]

    police = await client.get("/api/v1/analytics/police-attendance-profile")
    assert police.status_code == 200
    police_rows = {row["police_attended"]: row for row in police.json()["data"]}
    assert police_rows[True]["total_accidents"] == 4
    assert police_rows[False]["total_accidents"] == 1

    multi = await client.get("/api/v1/analytics/multi-vehicle-severity")
    assert multi.status_code == 200
    assert multi.json()["data"] == [
        {
            "collision_type": "Single vehicle",
            "speed_limit": None,
            "total_accidents": 5,
            "fatal": 2,
            "serious": 2,
            "slight": 1,
            "fatal_rate_pct": 40.0,
            "avg_casualties_per_accident": 1.0,
        }
    ]


async def test_multi_vehicle_severity_group_by_speed_limit_path(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    response = await client.get(
        "/api/v1/analytics/multi-vehicle-severity",
        params={"group_by_speed_limit": "true"},
    )
    assert response.status_code == 200
    rows = {(row["collision_type"], row["speed_limit"]): row for row in response.json()["data"]}
    assert rows[("Single vehicle", 20)]["total_accidents"] == 1
    assert rows[("Single vehicle", 30)]["total_accidents"] == 1
    assert rows[("Single vehicle", 40)]["total_accidents"] == 2
    assert rows[("Single vehicle", 60)]["total_accidents"] == 1


async def test_vulnerable_road_users_filters_with_pedestrian_and_cyclist_data(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")
    await db_session.execute(
        insert(Casualty),
        [
            {
                "id": 9001,
                "accident_id": "2022010012345",
                "vehicle_ref": 1,
                "casualty_ref": 2,
                "severity_id": 2,
                "casualty_class": "Passenger",
                "casualty_type": "Cyclist",
                "sex": "Male",
                "age": 22,
                "age_band": "21-25",
            },
            {
                "id": 9002,
                "accident_id": "2022010012348",
                "vehicle_ref": None,
                "casualty_ref": 2,
                "severity_id": 1,
                "casualty_class": "Pedestrian",
                "casualty_type": "Pedestrian",
                "sex": "Female",
                "age": 45,
                "age_band": "36-45",
            },
        ],
    )
    await db_session.flush()

    response = await client.get("/api/v1/analytics/vulnerable-road-users")
    assert response.status_code == 200
    rows = {(row["speed_limit"], row["urban_or_rural"]): row for row in response.json()["data"]}
    assert rows[(30, "Urban")] == {
        "speed_limit": 30,
        "urban_or_rural": "Urban",
        "total_casualties": 1,
        "fatal_casualties": 0,
        "serious_casualties": 1,
        "fatal_rate_pct": 0.0,
    }
    assert rows[(60, "Rural")] == {
        "speed_limit": 60,
        "urban_or_rural": "Rural",
        "total_casualties": 1,
        "fatal_casualties": 1,
        "serious_casualties": 0,
        "fatal_rate_pct": 100.0,
    }

    pedestrians_only = await client.get(
        "/api/v1/analytics/vulnerable-road-users",
        params={"casualty_type": "Pedestrian"},
    )
    assert pedestrians_only.status_code == 200
    assert pedestrians_only.json()["data"] == [rows[(60, "Rural")]]


async def test_hotspots_returns_cell_counts_and_respects_severity_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    response = await client.get(
        "/api/v1/analytics/hotspots",
        params={"lat": 53.8008, "lng": -1.5491, "radius_km": 0.1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == {
        "lat": 53.8008,
        "lng": -1.5491,
        "radius_km": 0.1,
        "severity": None,
        "date_from": None,
        "date_to": None,
    }
    assert body["data"] == [
        {
            "cell_lat": 53.805,
            "cell_lng": -1.545,
            "accident_count": 1,
            "fatal_count": 0,
            "serious_count": 1,
        }
    ]

    fatal_only = await client.get(
        "/api/v1/analytics/hotspots",
        params={"lat": 53.8008, "lng": -1.5491, "radius_km": 0.1, "severity": 1},
    )
    assert fatal_only.status_code == 200
    assert fatal_only.json()["data"] == []


async def test_weather_correlation_precipitation_returns_expected_bands(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    response = await client.get(
        "/api/v1/analytics/weather-correlation",
        params={"metric": "precipitation"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == {
        "metric": "precipitation",
        "date_from": None,
        "date_to": None,
        "region_id": None,
    }

    rows = {row["band"]: row for row in body["data"]}
    assert rows["Dry"] == {
        "band": "Dry",
        "band_range": "<0.2mm",
        "total_accidents": 2,
        "fatal": 1,
        "serious": 0,
        "slight": 1,
        "fatal_rate_pct": 50.0,
        "coverage_pct": 66.67,
    }
    assert rows["Light"] == {
        "band": "Light",
        "band_range": "0.2-2mm",
        "total_accidents": 1,
        "fatal": 0,
        "serious": 1,
        "slight": 0,
        "fatal_rate_pct": 0.0,
        "coverage_pct": 33.33,
    }

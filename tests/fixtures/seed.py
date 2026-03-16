from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Accident,
    Casualty,
    Cluster,
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

FixtureProfile = Literal["minimal_crud", "analytics_route_risk"]


async def seed_profile(session: AsyncSession, profile: FixtureProfile) -> None:
    """Load deterministic fixture data into the test database."""
    await session.execute(
        text(
            """
            TRUNCATE casualty, vehicle, accident, cluster, weather_observation, weather_station,
                     local_authority, region, severity, road_type, junction_detail,
                     light_condition, weather_condition, road_surface, vehicle_type
            RESTART IDENTITY CASCADE
            """
        )
    )

    for model, rows in _rows_for_profile(profile):
        if rows:
            await session.execute(insert(model), rows)

    await session.commit()


def _rows_for_profile(profile: FixtureProfile) -> list[tuple[type, list[dict[str, object]]]]:
    if profile == "minimal_crud":
        return _minimal_rows()
    return _analytics_route_risk_rows()


def _base_lookup_rows() -> list[tuple[type, list[dict[str, object]]]]:
    return [
        (Region, [{"id": 1, "name": "Yorkshire and The Humber"}]),
        (LocalAuthority, [{"id": 14, "name": "Leeds", "region_id": 1}]),
        (
            Severity,
            [
                {"id": 1, "label": "Fatal"},
                {"id": 2, "label": "Serious"},
                {"id": 3, "label": "Slight"},
            ],
        ),
        (
            RoadType,
            [
                {"id": 3, "label": "Single carriageway"},
                {"id": 6, "label": "Roundabout"},
            ],
        ),
        (
            JunctionDetail,
            [
                {"id": 3, "label": "T or staggered junction"},
                {"id": 6, "label": "Roundabout"},
            ],
        ),
        (
            LightCondition,
            [
                {"id": 1, "label": "Daylight"},
                {"id": 4, "label": "Darkness - lights lit"},
            ],
        ),
        (
            WeatherCondition,
            [
                {"id": 1, "label": "Fine no high winds"},
                {"id": 2, "label": "Raining no high winds"},
            ],
        ),
        (
            RoadSurface,
            [
                {"id": 1, "label": "Dry"},
                {"id": 2, "label": "Wet or damp"},
            ],
        ),
        (
            VehicleType,
            [
                {"id": 9, "label": "Car"},
                {"id": 11, "label": "Bus or coach"},
            ],
        ),
    ]


def _minimal_rows() -> list[tuple[type, list[dict[str, object]]]]:
    rows = _base_lookup_rows()
    rows.extend(
        [
            (
                WeatherStation,
                [
                    {
                        "id": 3802,
                        "name": "Leeds Bradford Airport",
                        "latitude": 53.8650,
                        "longitude": -1.6606,
                        "elevation_m": 208,
                        "active_from": date(2019, 1, 1),
                        "active_to": None,
                    }
                ],
            ),
            (
                WeatherObservation,
                [
                    {
                        "id": 1,
                        "station_id": 3802,
                        "observed_at": datetime(2022, 3, 15, 8, 0, 0),
                        "temperature_c": 8.1,
                        "precipitation_mm": 1.4,
                        "wind_speed_ms": 5.2,
                        "visibility_m": 4800,
                    }
                ],
            ),
            (
                Cluster,
                [
                    {
                        "id": 14,
                        "centroid_lat": 53.8001,
                        "centroid_lng": -1.5493,
                        "radius_km": 0.8,
                        "accident_count": 24,
                        "fatal_count": 1,
                        "serious_count": 4,
                        "fatal_rate_pct": 4.17,
                        "severity_label": "High",
                        "local_authority_id": 14,
                    }
                ],
            ),
            (
                Accident,
                [
                    {
                        "id": "2022010012345",
                        "date": date(2022, 3, 15),
                        "time": time(8, 42, 0),
                        "day_of_week": 2,
                        "latitude": 53.8008,
                        "longitude": -1.5491,
                        "local_authority_id": 14,
                        "severity_id": 2,
                        "road_type_id": 3,
                        "junction_detail_id": 3,
                        "light_condition_id": 1,
                        "weather_condition_id": 2,
                        "road_surface_id": 2,
                        "speed_limit": 30,
                        "urban_or_rural": "Urban",
                        "police_attended": True,
                        "number_of_vehicles": 1,
                        "number_of_casualties": 1,
                        "weather_observation_id": 1,
                        "cluster_id": 14,
                    }
                ],
            ),
            (
                Vehicle,
                [
                    {
                        "id": 1,
                        "accident_id": "2022010012345",
                        "vehicle_ref": 1,
                        "vehicle_type_id": 9,
                        "age_of_driver": 34,
                        "sex_of_driver": "Male",
                        "engine_capacity_cc": 1600,
                        "propulsion_code": "Petrol",
                        "age_of_vehicle": 5,
                        "journey_purpose": "Commute",
                    }
                ],
            ),
            (
                Casualty,
                [
                    {
                        "id": 1,
                        "accident_id": "2022010012345",
                        "vehicle_ref": 1,
                        "casualty_ref": 1,
                        "severity_id": 2,
                        "casualty_class": "Driver",
                        "casualty_type": "Car occupant",
                        "sex": "Male",
                        "age": 34,
                        "age_band": "26-35",
                    }
                ],
            ),
        ]
    )
    return rows


def _analytics_route_risk_rows() -> list[tuple[type, list[dict[str, object]]]]:
    rows = _base_lookup_rows()
    rows.extend(
        [
            (
                WeatherStation,
                [
                    {
                        "id": 3802,
                        "name": "Leeds Bradford Airport",
                        "latitude": 53.8650,
                        "longitude": -1.6606,
                        "elevation_m": 208,
                        "active_from": date(2019, 1, 1),
                        "active_to": None,
                    }
                ],
            ),
            (
                WeatherObservation,
                [
                    {
                        "id": 1,
                        "station_id": 3802,
                        "observed_at": datetime(2022, 3, 15, 8, 0, 0),
                        "temperature_c": 8.1,
                        "precipitation_mm": 1.4,
                        "wind_speed_ms": 5.2,
                        "visibility_m": 4800,
                    },
                    {
                        "id": 2,
                        "station_id": 3802,
                        "observed_at": datetime(2022, 3, 18, 17, 0, 0),
                        "temperature_c": 6.4,
                        "precipitation_mm": 0.0,
                        "wind_speed_ms": 6.7,
                        "visibility_m": 8000,
                    },
                ],
            ),
            (
                Cluster,
                [
                    {
                        "id": 14,
                        "centroid_lat": 53.8001,
                        "centroid_lng": -1.5493,
                        "radius_km": 0.8,
                        "accident_count": 24,
                        "fatal_count": 1,
                        "serious_count": 4,
                        "fatal_rate_pct": 4.17,
                        "severity_label": "High",
                        "local_authority_id": 14,
                    },
                    {
                        "id": 15,
                        "centroid_lat": 53.7909,
                        "centroid_lng": -1.5410,
                        "radius_km": 0.5,
                        "accident_count": 11,
                        "fatal_count": 0,
                        "serious_count": 2,
                        "fatal_rate_pct": 0.0,
                        "severity_label": "Low",
                        "local_authority_id": 14,
                    },
                ],
            ),
            (
                Accident,
                [
                    {
                        "id": "2022010012345",
                        "date": date(2022, 3, 15),
                        "time": time(8, 42, 0),
                        "day_of_week": 2,
                        "latitude": 53.8008,
                        "longitude": -1.5491,
                        "local_authority_id": 14,
                        "severity_id": 2,
                        "road_type_id": 3,
                        "junction_detail_id": 3,
                        "light_condition_id": 1,
                        "weather_condition_id": 2,
                        "road_surface_id": 2,
                        "speed_limit": 30,
                        "urban_or_rural": "Urban",
                        "police_attended": True,
                        "number_of_vehicles": 1,
                        "number_of_casualties": 1,
                        "weather_observation_id": 1,
                        "cluster_id": 14,
                    },
                    {
                        "id": "2022010012346",
                        "date": date(2022, 3, 18),
                        "time": time(17, 15, 0),
                        "day_of_week": 5,
                        "latitude": 53.7925,
                        "longitude": -1.5433,
                        "local_authority_id": 14,
                        "severity_id": 1,
                        "road_type_id": 3,
                        "junction_detail_id": 6,
                        "light_condition_id": 4,
                        "weather_condition_id": 1,
                        "road_surface_id": 1,
                        "speed_limit": 40,
                        "urban_or_rural": "Urban",
                        "police_attended": True,
                        "number_of_vehicles": 1,
                        "number_of_casualties": 1,
                        "weather_observation_id": 2,
                        "cluster_id": 15,
                    },
                    {
                        "id": "2022010012347",
                        "date": date(2022, 3, 18),
                        "time": time(17, 35, 0),
                        "day_of_week": 5,
                        "latitude": 53.7934,
                        "longitude": -1.5420,
                        "local_authority_id": 14,
                        "severity_id": 3,
                        "road_type_id": 3,
                        "junction_detail_id": 6,
                        "light_condition_id": 4,
                        "weather_condition_id": 1,
                        "road_surface_id": 1,
                        "speed_limit": 40,
                        "urban_or_rural": "Urban",
                        "police_attended": False,
                        "number_of_vehicles": 1,
                        "number_of_casualties": 1,
                        "weather_observation_id": 2,
                        "cluster_id": 15,
                    },
                    {
                        "id": "2022010012348",
                        "date": date(2022, 3, 20),
                        "time": time(2, 20, 0),
                        "day_of_week": 7,
                        "latitude": 53.7801,
                        "longitude": -1.5202,
                        "local_authority_id": 14,
                        "severity_id": 1,
                        "road_type_id": 3,
                        "junction_detail_id": 3,
                        "light_condition_id": 4,
                        "weather_condition_id": 2,
                        "road_surface_id": 2,
                        "speed_limit": 60,
                        "urban_or_rural": "Rural",
                        "police_attended": True,
                        "number_of_vehicles": 1,
                        "number_of_casualties": 1,
                        "weather_observation_id": None,
                        "cluster_id": None,
                    },
                    {
                        "id": "2022010012349",
                        "date": date(2022, 3, 21),
                        "time": time(8, 10, 0),
                        "day_of_week": 1,
                        "latitude": 53.8051,
                        "longitude": -1.5537,
                        "local_authority_id": 14,
                        "severity_id": 2,
                        "road_type_id": 3,
                        "junction_detail_id": 3,
                        "light_condition_id": 1,
                        "weather_condition_id": 1,
                        "road_surface_id": 1,
                        "speed_limit": 20,
                        "urban_or_rural": "Urban",
                        "police_attended": True,
                        "number_of_vehicles": 1,
                        "number_of_casualties": 1,
                        "weather_observation_id": None,
                        "cluster_id": None,
                    },
                ],
            ),
            (Vehicle, _child_rows("vehicle_ref")),
            (Casualty, _child_rows("casualty_ref")),
        ]
    )
    return rows


def _child_rows(ref_field: Literal["vehicle_ref", "casualty_ref"]) -> list[dict[str, object]]:
    accident_ids = [
        "2022010012345",
        "2022010012346",
        "2022010012347",
        "2022010012348",
        "2022010012349",
    ]

    if ref_field == "vehicle_ref":
        return [
            {
                "id": i,
                "accident_id": accident_id,
                "vehicle_ref": 1,
                "vehicle_type_id": 9,
                "age_of_driver": 30 + i,
                "sex_of_driver": "Male" if i % 2 else "Female",
                "engine_capacity_cc": 1600,
                "propulsion_code": "Petrol",
                "age_of_vehicle": 5,
                "journey_purpose": "Commute",
            }
            for i, accident_id in enumerate(accident_ids, start=1)
        ]

    severity_by_accident = {
        "2022010012345": 2,
        "2022010012346": 1,
        "2022010012347": 3,
        "2022010012348": 1,
        "2022010012349": 2,
    }
    age_band_by_accident = {
        "2022010012345": "26-35",
        "2022010012346": "36-45",
        "2022010012347": "21-25",
        "2022010012348": "46-55",
        "2022010012349": "16-20",
    }
    return [
        {
            "id": i,
            "accident_id": accident_id,
            "vehicle_ref": 1,
            "casualty_ref": 1,
            "severity_id": severity_by_accident[accident_id],
            "casualty_class": "Driver",
            "casualty_type": "Car occupant",
            "sex": "Male" if i % 2 else "Female",
            "age": 20 + i,
            "age_band": age_band_by_accident[accident_id],
        }
        for i, accident_id in enumerate(accident_ids, start=1)
    ]

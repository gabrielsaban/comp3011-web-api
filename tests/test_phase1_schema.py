import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures import seed_profile


async def test_phase1_tables_exist(db_session: AsyncSession) -> None:
    expected = {
        "accident",
        "casualty",
        "cluster",
        "junction_detail",
        "light_condition",
        "local_authority",
        "region",
        "road_surface",
        "road_type",
        "severity",
        "vehicle",
        "vehicle_type",
        "weather_condition",
        "weather_observation",
        "weather_station",
    }

    result = await db_session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    names = {row[0] for row in result.fetchall()}

    assert expected.issubset(names)


async def test_casualty_vehicle_composite_fk_enforced(db_session: AsyncSession) -> None:
    await seed_profile(db_session, "minimal_crud")

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                """
                INSERT INTO casualty (
                    accident_id, vehicle_ref, casualty_ref, severity_id, casualty_class
                )
                VALUES (:accident_id, :vehicle_ref, :casualty_ref, :severity_id, :casualty_class)
                """
            ),
            {
                "accident_id": "2022010012345",
                "vehicle_ref": 999,
                "casualty_ref": 2,
                "severity_id": 2,
                "casualty_class": "Passenger",
            },
        )
        await db_session.flush()


async def test_analytics_route_risk_profile_shape(db_session: AsyncSession) -> None:
    await seed_profile(db_session, "analytics_route_risk")

    total = await db_session.scalar(text("SELECT COUNT(*) FROM accident"))
    null_weather = await db_session.scalar(
        text("SELECT COUNT(*) FROM accident WHERE weather_observation_id IS NULL")
    )
    null_cluster = await db_session.scalar(
        text("SELECT COUNT(*) FROM accident WHERE cluster_id IS NULL")
    )

    assert total == 5
    assert null_weather and null_weather > 0
    assert null_cluster and null_cluster > 0

"""create phase1 core schema

Revision ID: 81fd3948f942
Revises:
Create Date: 2026-03-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81fd3948f942"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Lookup tables.
    op.create_table(
        "region",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "local_authority",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "severity",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "road_type",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "junction_detail",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "light_condition",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "weather_condition",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "road_surface",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vehicle_type",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Weather enrichment tables.
    op.create_table(
        "weather_station",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("latitude", postgresql.DOUBLE_PRECISION(precision=53), nullable=False),
        sa.Column("longitude", postgresql.DOUBLE_PRECISION(precision=53), nullable=False),
        sa.Column("elevation_m", sa.Integer(), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=True),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "weather_observation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("temperature_c", sa.REAL(), nullable=True),
        sa.Column("precipitation_mm", sa.REAL(), nullable=True),
        sa.Column("wind_speed_ms", sa.REAL(), nullable=True),
        sa.Column("visibility_m", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["station_id"], ["weather_station.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_obs_station_time",
        "weather_observation",
        ["station_id", "observed_at"],
        unique=False,
    )

    # Cluster table (required before accident for inline FK declaration).
    op.create_table(
        "cluster",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("centroid_lat", postgresql.DOUBLE_PRECISION(precision=53), nullable=False),
        sa.Column("centroid_lng", postgresql.DOUBLE_PRECISION(precision=53), nullable=False),
        sa.Column("radius_km", sa.REAL(), nullable=False),
        sa.Column("accident_count", sa.Integer(), nullable=False),
        sa.Column("fatal_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("serious_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fatal_rate_pct", sa.REAL(), nullable=False),
        sa.Column("severity_label", sa.Text(), nullable=False),
        sa.Column("local_authority_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["local_authority_id"], ["local_authority.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_cluster_centroid",
        "cluster",
        ["centroid_lat", "centroid_lng"],
        unique=False,
    )

    # Core accident/vehicle/casualty tables.
    op.create_table(
        "accident",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=True),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=True),
        sa.Column("latitude", postgresql.DOUBLE_PRECISION(precision=53), nullable=True),
        sa.Column("longitude", postgresql.DOUBLE_PRECISION(precision=53), nullable=True),
        sa.Column("local_authority_id", sa.Integer(), nullable=True),
        sa.Column("severity_id", sa.Integer(), nullable=False),
        sa.Column("road_type_id", sa.Integer(), nullable=True),
        sa.Column("junction_detail_id", sa.Integer(), nullable=True),
        sa.Column("light_condition_id", sa.Integer(), nullable=True),
        sa.Column("weather_condition_id", sa.Integer(), nullable=True),
        sa.Column("road_surface_id", sa.Integer(), nullable=True),
        sa.Column("speed_limit", sa.SmallInteger(), nullable=True),
        sa.Column("urban_or_rural", sa.Text(), nullable=True),
        sa.Column("police_attended", sa.Boolean(), nullable=True),
        sa.Column(
            "number_of_vehicles",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "number_of_casualties",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("weather_observation_id", sa.Integer(), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster.id"]),
        sa.ForeignKeyConstraint(["junction_detail_id"], ["junction_detail.id"]),
        sa.ForeignKeyConstraint(["light_condition_id"], ["light_condition.id"]),
        sa.ForeignKeyConstraint(["local_authority_id"], ["local_authority.id"]),
        sa.ForeignKeyConstraint(["road_surface_id"], ["road_surface.id"]),
        sa.ForeignKeyConstraint(["road_type_id"], ["road_type.id"]),
        sa.ForeignKeyConstraint(["severity_id"], ["severity.id"]),
        sa.ForeignKeyConstraint(["weather_condition_id"], ["weather_condition.id"]),
        sa.ForeignKeyConstraint(["weather_observation_id"], ["weather_observation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_accident_lat", "accident", ["latitude"], unique=False)
    op.create_index("idx_accident_lng", "accident", ["longitude"], unique=False)
    op.create_index("idx_accident_lat_lng", "accident", ["latitude", "longitude"], unique=False)
    op.create_index("idx_accident_date", "accident", ["date"], unique=False)
    op.create_index("idx_accident_severity", "accident", ["severity_id"], unique=False)
    op.create_index("idx_accident_la", "accident", ["local_authority_id"], unique=False)
    op.create_index("idx_accident_cluster", "accident", ["cluster_id"], unique=False)
    op.create_index(
        "idx_accident_obs",
        "accident",
        ["weather_observation_id"],
        unique=False,
    )

    op.create_table(
        "vehicle",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("accident_id", sa.String(), nullable=False),
        sa.Column("vehicle_ref", sa.SmallInteger(), nullable=False),
        sa.Column("vehicle_type_id", sa.Integer(), nullable=True),
        sa.Column("age_of_driver", sa.SmallInteger(), nullable=True),
        sa.Column("sex_of_driver", sa.Text(), nullable=True),
        sa.Column("engine_capacity_cc", sa.Integer(), nullable=True),
        sa.Column("propulsion_code", sa.Text(), nullable=True),
        sa.Column("age_of_vehicle", sa.SmallInteger(), nullable=True),
        sa.Column("journey_purpose", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["accident_id"], ["accident.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_type_id"], ["vehicle_type.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accident_id", "vehicle_ref"),
    )
    op.create_index("idx_vehicle_accident", "vehicle", ["accident_id"], unique=False)

    op.create_table(
        "casualty",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("accident_id", sa.String(), nullable=False),
        sa.Column("vehicle_ref", sa.SmallInteger(), nullable=True),
        sa.Column("casualty_ref", sa.SmallInteger(), nullable=False),
        sa.Column("severity_id", sa.Integer(), nullable=False),
        sa.Column("casualty_class", sa.Text(), nullable=True),
        sa.Column("casualty_type", sa.Text(), nullable=True),
        sa.Column("sex", sa.Text(), nullable=True),
        sa.Column("age", sa.SmallInteger(), nullable=True),
        sa.Column("age_band", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["accident_id"], ["accident.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["accident_id", "vehicle_ref"],
            ["vehicle.accident_id", "vehicle.vehicle_ref"],
            name="fk_casualty_vehicle_ref",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        sa.ForeignKeyConstraint(["severity_id"], ["severity.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accident_id", "casualty_ref"),
    )
    op.create_index("idx_casualty_accident", "casualty", ["accident_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_casualty_accident", table_name="casualty")
    op.drop_table("casualty")

    op.drop_index("idx_vehicle_accident", table_name="vehicle")
    op.drop_table("vehicle")

    op.drop_index("idx_accident_obs", table_name="accident")
    op.drop_index("idx_accident_cluster", table_name="accident")
    op.drop_index("idx_accident_la", table_name="accident")
    op.drop_index("idx_accident_severity", table_name="accident")
    op.drop_index("idx_accident_date", table_name="accident")
    op.drop_index("idx_accident_lat_lng", table_name="accident")
    op.drop_index("idx_accident_lng", table_name="accident")
    op.drop_index("idx_accident_lat", table_name="accident")
    op.drop_table("accident")

    op.drop_index("idx_cluster_centroid", table_name="cluster")
    op.drop_table("cluster")

    op.drop_index("idx_obs_station_time", table_name="weather_observation")
    op.drop_table("weather_observation")
    op.drop_table("weather_station")

    op.drop_table("vehicle_type")
    op.drop_table("road_surface")
    op.drop_table("weather_condition")
    op.drop_table("light_condition")
    op.drop_table("junction_detail")
    op.drop_table("road_type")
    op.drop_table("severity")
    op.drop_table("local_authority")
    op.drop_table("region")

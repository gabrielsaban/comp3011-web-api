"""add weather observation unique key

Revision ID: 4b8c4f5d9f7d
Revises: 81fd3948f942
Create Date: 2026-03-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b8c4f5d9f7d"
down_revision: str | None = "81fd3948f942"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Defensive deduplication before enforcing deterministic station/time key.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY station_id, observed_at
                    ORDER BY id DESC
                ) AS rn
            FROM weather_observation
        )
        DELETE FROM weather_observation target
        USING ranked source
        WHERE target.id = source.id
          AND source.rn > 1
        """
    )
    op.drop_index("idx_obs_station_time", table_name="weather_observation")
    op.create_unique_constraint(
        "uq_weather_observation_station_time",
        "weather_observation",
        ["station_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_weather_observation_station_time",
        "weather_observation",
        type_="unique",
    )
    op.create_index(
        "idx_obs_station_time",
        "weather_observation",
        ["station_id", "observed_at"],
        unique=False,
    )

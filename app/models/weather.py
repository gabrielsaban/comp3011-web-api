from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import REAL, Date, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WeatherStation(Base):
    __tablename__ = "weather_station"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(DOUBLE_PRECISION(precision=53), nullable=False)
    longitude: Mapped[float] = mapped_column(DOUBLE_PRECISION(precision=53), nullable=False)
    elevation_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    observations: Mapped[list[WeatherObservation]] = relationship(back_populates="station")


class WeatherObservation(Base):
    __tablename__ = "weather_observation"
    __table_args__ = (Index("idx_obs_station_time", "station_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("weather_station.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(REAL, nullable=True)
    precipitation_mm: Mapped[float | None] = mapped_column(REAL, nullable=True)
    wind_speed_ms: Mapped[float | None] = mapped_column(REAL, nullable=True)
    visibility_m: Mapped[int | None] = mapped_column(Integer, nullable=True)

    station: Mapped[WeatherStation] = relationship(back_populates="observations")

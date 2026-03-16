from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.lookups import (
        JunctionDetail,
        LightCondition,
        LocalAuthority,
        RoadSurface,
        RoadType,
        Severity,
        VehicleType,
        WeatherCondition,
    )
    from app.models.weather import WeatherObservation


class Accident(Base):
    __tablename__ = "accident"
    __table_args__ = (
        Index("idx_accident_lat", "latitude"),
        Index("idx_accident_lng", "longitude"),
        Index("idx_accident_lat_lng", "latitude", "longitude"),
        Index("idx_accident_date", "date"),
        Index("idx_accident_severity", "severity_id"),
        Index("idx_accident_la", "local_authority_id"),
        Index("idx_accident_cluster", "cluster_id"),
        Index("idx_accident_obs", "weather_observation_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[time | None] = mapped_column(nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    latitude: Mapped[float | None] = mapped_column(DOUBLE_PRECISION(precision=53), nullable=True)
    longitude: Mapped[float | None] = mapped_column(DOUBLE_PRECISION(precision=53), nullable=True)
    local_authority_id: Mapped[int | None] = mapped_column(
        ForeignKey("local_authority.id"),
        nullable=True,
    )
    severity_id: Mapped[int] = mapped_column(ForeignKey("severity.id"), nullable=False)
    road_type_id: Mapped[int | None] = mapped_column(ForeignKey("road_type.id"), nullable=True)
    junction_detail_id: Mapped[int | None] = mapped_column(
        ForeignKey("junction_detail.id"),
        nullable=True,
    )
    light_condition_id: Mapped[int | None] = mapped_column(
        ForeignKey("light_condition.id"),
        nullable=True,
    )
    weather_condition_id: Mapped[int | None] = mapped_column(
        ForeignKey("weather_condition.id"),
        nullable=True,
    )
    road_surface_id: Mapped[int | None] = mapped_column(
        ForeignKey("road_surface.id"),
        nullable=True,
    )
    speed_limit: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    urban_or_rural: Mapped[str | None] = mapped_column(Text, nullable=True)
    police_attended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    number_of_vehicles: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    number_of_casualties: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    weather_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("weather_observation.id"),
        nullable=True,
    )
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("cluster.id"), nullable=True)

    local_authority: Mapped[LocalAuthority | None] = relationship()
    severity: Mapped[Severity] = relationship()
    road_type: Mapped[RoadType | None] = relationship()
    junction_detail: Mapped[JunctionDetail | None] = relationship()
    light_condition: Mapped[LightCondition | None] = relationship()
    weather_condition: Mapped[WeatherCondition | None] = relationship()
    road_surface: Mapped[RoadSurface | None] = relationship()
    weather_observation: Mapped[WeatherObservation | None] = relationship()
    vehicles: Mapped[list[Vehicle]] = relationship(back_populates="accident")
    casualties: Mapped[list[Casualty]] = relationship(back_populates="accident")
    cluster: Mapped[Cluster | None] = relationship(back_populates="accidents")


class Vehicle(Base):
    __tablename__ = "vehicle"
    __table_args__ = (
        UniqueConstraint("accident_id", "vehicle_ref"),
        Index("idx_vehicle_accident", "accident_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    accident_id: Mapped[str] = mapped_column(
        ForeignKey("accident.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_ref: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vehicle_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle_type.id"),
        nullable=True,
    )
    age_of_driver: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sex_of_driver: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_capacity_cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    propulsion_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_of_vehicle: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    journey_purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    accident: Mapped[Accident] = relationship(back_populates="vehicles")
    vehicle_type: Mapped[VehicleType | None] = relationship()


class Casualty(Base):
    __tablename__ = "casualty"
    __table_args__ = (
        ForeignKeyConstraint(
            ["accident_id", "vehicle_ref"],
            ["vehicle.accident_id", "vehicle.vehicle_ref"],
            name="fk_casualty_vehicle_ref",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        UniqueConstraint("accident_id", "casualty_ref"),
        Index("idx_casualty_accident", "accident_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    accident_id: Mapped[str] = mapped_column(
        ForeignKey("accident.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_ref: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    casualty_ref: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    severity_id: Mapped[int] = mapped_column(ForeignKey("severity.id"), nullable=False)
    casualty_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    casualty_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    sex: Mapped[str | None] = mapped_column(Text, nullable=True)
    age: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    age_band: Mapped[str | None] = mapped_column(Text, nullable=True)

    accident: Mapped[Accident] = relationship(back_populates="casualties")
    severity: Mapped[Severity] = relationship()

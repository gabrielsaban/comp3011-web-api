from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Region(Base):
    __tablename__ = "region"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    local_authorities: Mapped[list[LocalAuthority]] = relationship(
        back_populates="region",
        cascade="all, delete-orphan",
    )


class LocalAuthority(Base):
    __tablename__ = "local_authority"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), nullable=False)

    region: Mapped[Region] = relationship(back_populates="local_authorities")


class Severity(Base):
    __tablename__ = "severity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class RoadType(Base):
    __tablename__ = "road_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class JunctionDetail(Base):
    __tablename__ = "junction_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class LightCondition(Base):
    __tablename__ = "light_condition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class WeatherCondition(Base):
    __tablename__ = "weather_condition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class RoadSurface(Base):
    __tablename__ = "road_surface"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class VehicleType(Base):
    __tablename__ = "vehicle_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)

from __future__ import annotations

from sqlalchemy import REAL, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Cluster(Base):
    __tablename__ = "cluster"
    __table_args__ = (Index("idx_cluster_centroid", "centroid_lat", "centroid_lng"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    centroid_lat: Mapped[float] = mapped_column(nullable=False)
    centroid_lng: Mapped[float] = mapped_column(nullable=False)
    radius_km: Mapped[float] = mapped_column(REAL, nullable=False)
    accident_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fatal_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    serious_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    fatal_rate_pct: Mapped[float] = mapped_column(REAL, nullable=False)
    severity_label: Mapped[str] = mapped_column(Text, nullable=False)
    local_authority_id: Mapped[int | None] = mapped_column(
        ForeignKey("local_authority.id"),
        nullable=True,
    )

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # ponytail: plain string, not an Enum table. Three roles that never change.
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Metric(Base):
    """One normalized measurement.

    ponytail: a single narrow table instead of body/nutrition/training/sleep tables.
    Every source we ingest (Withings, Apple Health, Health Connect, CSV) already emits
    exactly this shape: type + value + unit + timestamp + origin. Ceiling: it holds
    scalars only — when the UI needs per-exercise sets/reps or per-meal foods, those get
    their own table and keep writing their daily rollups here.
    """

    __tablename__ = "metrics"
    __table_args__ = (
        # Re-syncing a provider must not duplicate rows.
        UniqueConstraint("user_id", "source", "metric", "ts", name="uq_metric_point"),
        Index("ix_metrics_user_metric_ts", "user_id", "metric", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailySnapshot(Base):
    """Nightly per-user rollup. `data` is whatever analytics computed that day."""

    __tablename__ = "daily_snapshots"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


ROLES = ("user", "coach", "admin")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

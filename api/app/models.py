from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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


class UserSetting(Base):
    """A per-user configuration value — the user's own API keys, mostly.

    Secret values are stored encrypted (see crypto.py) and are never returned by the
    API; the settings page shows a masked hint instead.
    """

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[str] = mapped_column(String(2048))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProviderConnection(Base):
    """OAuth tokens for one user at one provider (withings, garmin, ...).

    ponytail: tokens are stored as-is. The DB is single-tenant on the app's own VM and
    never exposed, so column encryption buys little until the DB moves or is shared —
    at that point wrap access_token/refresh_token in Fernet keyed from the env.
    """

    __tablename__ = "provider_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_connection"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_user_id: Mapped[str] = mapped_column(String(64))
    access_token: Mapped[str] = mapped_column(String(512))
    refresh_token: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Provider-side high-water mark, so a sync only asks for what changed. 0 = never synced.
    last_update: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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

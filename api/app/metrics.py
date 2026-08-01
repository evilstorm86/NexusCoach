from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user
from .db import get_db
from .models import Metric, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


class MetricIn(BaseModel):
    ts: datetime
    metric: str = Field(min_length=1, max_length=64)
    value: float
    unit: str = Field(max_length=16)
    source: str = Field(default="manual", max_length=32)


class MetricOut(MetricIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


def upsert(db: Session, user_id: int, points: list[MetricIn]) -> dict:
    """Idempotent write: re-sending the same point updates it instead of duplicating.

    Every ingest path — manual, provider sync, CSV import — goes through here.

    ponytail: read-then-write per point rather than a dialect-specific ON CONFLICT.
    Ceiling is a query per point — batch it if a provider ever backfills 100k rows.
    """
    written = 0
    for p in points:
        existing = db.scalar(
            select(Metric).where(
                Metric.user_id == user_id,
                Metric.source == p.source,
                Metric.metric == p.metric,
                Metric.ts == p.ts,
            )
        )
        if existing:
            existing.value, existing.unit = p.value, p.unit
        else:
            db.add(Metric(user_id=user_id, **p.model_dump()))
            written += 1
    db.commit()
    return {"received": len(points), "created": written, "updated": len(points) - written}


@router.post("", status_code=201)
def ingest(
    points: list[MetricIn],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return upsert(db, user.id, points)


@router.get("", response_model=list[MetricOut])
def list_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    metric: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=500, le=5000),
):
    q = select(Metric).where(Metric.user_id == user.id)  # never unscoped
    if metric:
        q = q.where(Metric.metric == metric)
    if since:
        q = q.where(Metric.ts >= since)
    if until:
        q = q.where(Metric.ts <= until)
    return db.scalars(q.order_by(Metric.ts.desc()).limit(limit)).all()

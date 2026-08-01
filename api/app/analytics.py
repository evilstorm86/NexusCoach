"""Trends, daily snapshots and projections.

The three answer kinds the AI coach must never blur (spec §8) are separated here at the
source, not in the prompt:

  facts      — what was measured
  analysis   — what the measurements imply (smoothing, rate of change, fit quality)
  prediction — extrapolation, always with the assumption stated

ponytail: statistics.linear_regression and a time-weighted EMA, not pandas/sklearn/XGBoost.
One person's data is ~365 points per metric per year — the stdlib fits it exactly, and the
ML stack would cost ~500 MB of image and a big chunk of a 2 GB VM to do the same job.
Ceiling: this is linear. Anything needing seasonality, multi-metric interaction or a real
model (e.g. predicting recovery from HRV + load) is where numpy/sklearn earns its weight.
"""

import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user
from .db import get_db
from .models import DailySnapshot, Metric, User, utcnow

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Metrics summarised on the dashboard, and how a day's readings collapse to one number.
DAILY_AGG = {
    "steps": sum,
    "active_kcal": sum,
    "basal_kcal": sum,
    "kcal_in": sum,
    "protein_g": sum,
    "carbs_g": sum,
    "fat_g": sum,
    "distance_km": sum,
    "exercise_min": sum,
}
HEADLINE_METRICS = ("weight", "fat_ratio", "muscle_mass", "resting_hr", "hrv", "steps", "kcal_in")
EMA_HALF_LIFE_DAYS = 10.0
TREND_WINDOW_DAYS = 28


def aggregate_day(metric: str, values: list[float]) -> float:
    return DAILY_AGG.get(metric, statistics.fmean)(values)


def series(db: Session, user_id: int, metric: str, days: int) -> list[tuple[datetime, float]]:
    """One value per day, oldest first. Always scoped to the user."""
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(Metric.ts, Metric.value)
        .where(Metric.user_id == user_id, Metric.metric == metric, Metric.ts >= since)
        .order_by(Metric.ts)
    ).all()

    by_day: dict[date, list[float]] = defaultdict(list)
    for ts, value in rows:
        if ts.tzinfo is None:  # sqlite returns naive datetimes
            ts = ts.replace(tzinfo=timezone.utc)
        by_day[ts.astimezone(timezone.utc).date()].append(value)

    return [
        (datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc), aggregate_day(metric, v))
        for day, v in sorted(by_day.items())
    ]


def ema(points: list[tuple[datetime, float]], half_life_days: float = EMA_HALF_LIFE_DAYS):
    """Time-weighted EMA, so a gap in readings decays the old value correctly.

    Daily weight is mostly water noise; the smoothed line is what actually moves.
    """
    smoothed = []
    current = None
    previous_ts = None
    for ts, value in points:
        if current is None:
            current = value
        else:
            gap_days = (ts - previous_ts).total_seconds() / 86400
            alpha = 1 - 0.5 ** (gap_days / half_life_days)
            current += alpha * (value - current)
        previous_ts = ts
        smoothed.append((ts, current))
    return smoothed


def trend(points: list[tuple[datetime, float]], window_days: int = TREND_WINDOW_DAYS):
    """Least-squares slope over the recent window, in units per week.

    Returns None when there is not enough spread to fit a line — an honest "don't know"
    beats a slope drawn through two points.
    """
    if len(points) < 2:
        return None
    cutoff = points[-1][0] - timedelta(days=window_days)
    window = [p for p in points if p[0] >= cutoff]
    if len(window) < 3:
        return None

    origin = window[0][0]
    x = [(ts - origin).total_seconds() / 86400 for ts, _ in window]
    y = [v for _, v in window]
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None

    slope, intercept = statistics.linear_regression(x, y)
    r = statistics.correlation(x, y)
    return {
        "per_week": round(slope * 7, 3),
        "r_squared": round(r * r, 3),
        "days": round(x[-1] - x[0], 1),
        "points": len(window),
        "_slope_per_day": slope,
        "_intercept": intercept,
        "_origin": origin,
    }


def _public(t: dict | None) -> dict | None:
    return None if t is None else {k: v for k, v in t.items() if not k.startswith("_")}


def summarize(db: Session, user_id: int, days: int = 90) -> dict:
    facts, analysis = {}, {}
    for metric in HEADLINE_METRICS:
        points = series(db, user_id, metric, days)
        if not points:
            continue
        ts, value = points[-1]
        facts[metric] = {"latest": round(value, 3), "at": ts.isoformat(), "days_of_data": len(points)}
        smoothed = ema(points)
        analysis[metric] = {
            "smoothed": round(smoothed[-1][1], 3),
            "trend": _public(trend(points)),
        }
    return {"facts": facts, "analysis": analysis}


def project(points: list[tuple[datetime, float]], goal: float | None, days_ahead: int | None):
    """Extrapolate the current trend. Linear, and says so."""
    t = trend(points)
    if t is None:
        return {"available": False, "reason": "not enough data to fit a trend"}

    # Start from the fitted value at the last reading, not the EMA: the EMA lags a steady
    # trend by about its half-life, which would bias every projection.
    slope = t["_slope_per_day"]
    fitted_now = t["_intercept"] + slope * t["days"]
    out = {
        "available": True,
        "basis": f"linear fit over the last {t['days']} days ({t['points']} readings)",
        "assumption": "current rate of change continues unchanged",
        "r_squared": t["r_squared"],
    }

    if days_ahead:
        out["value_in_days"] = {
            "days": days_ahead,
            "value": round(fitted_now + slope * days_ahead, 2),
        }
    if goal is not None:
        remaining = goal - fitted_now
        if abs(slope) < 1e-6 or remaining * slope < 0:
            out["goal"] = {"target": goal, "reachable": False, "reason": "trend is flat or moving away"}
        else:
            eta_days = remaining / slope
            out["goal"] = {
                "target": goal,
                "reachable": True,
                "days": round(eta_days),
                "date": (utcnow() + timedelta(days=eta_days)).date().isoformat(),
            }
    return out


def build_snapshot(db: Session, user_id: int, day: date | None = None) -> DailySnapshot:
    """Recompute one day's rollup. Idempotent — the nightly job just re-runs it."""
    day = day or utcnow().date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    rows = db.execute(
        select(Metric.metric, Metric.value).where(
            Metric.user_id == user_id, Metric.ts >= start, Metric.ts < start + timedelta(days=1)
        )
    ).all()

    values: dict[str, list[float]] = defaultdict(list)
    for metric, value in rows:
        values[metric].append(value)

    data = {
        "metrics": {m: round(aggregate_day(m, v), 3) for m, v in values.items()},
        "analysis": summarize(db, user_id)["analysis"],
        "computed_at": utcnow().isoformat(),
    }
    if {"kcal_in", "active_kcal", "basal_kcal"} & values.keys():
        burned = data["metrics"].get("active_kcal", 0) + data["metrics"].get("basal_kcal", 0)
        data["energy_balance"] = round(data["metrics"].get("kcal_in", 0) - burned, 1)

    snapshot = db.get(DailySnapshot, (user_id, day)) or DailySnapshot(user_id=user_id, day=day)
    snapshot.data = data
    db.merge(snapshot)
    db.commit()
    return snapshot


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    days: int = Query(default=90, ge=1, le=1825),
):
    return summarize(db, user.id, days)


@router.get("/series")
def get_series(
    metric: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    days: int = Query(default=90, ge=1, le=1825),
):
    points = series(db, user.id, metric, days)
    smoothed = dict(ema(points))
    return {
        "metric": metric,
        "facts": [{"ts": ts.isoformat(), "value": round(v, 3)} for ts, v in points],
        "analysis": {
            "smoothed": [{"ts": ts.isoformat(), "value": round(v, 3)} for ts, v in smoothed.items()],
            "trend": _public(trend(points)),
        },
    }


@router.get("/predict")
def get_prediction(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    metric: str = "weight",
    goal: float | None = None,
    days_ahead: int | None = Query(default=None, ge=1, le=730),
    days: int = Query(default=90, ge=1, le=1825),
):
    if goal is None and days_ahead is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pass goal and/or days_ahead")
    return {"metric": metric, "prediction": project(series(db, user.id, metric, days), goal, days_ahead)}


@router.post("/snapshot", status_code=201)
def post_snapshot(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    day: date | None = None,
):
    snapshot = build_snapshot(db, user.id, day)
    return {"day": snapshot.day.isoformat(), "data": snapshot.data}


@router.get("/snapshots")
def get_snapshots(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    days: int = Query(default=30, ge=1, le=365),
):
    since = utcnow().date() - timedelta(days=days)
    rows = db.scalars(
        select(DailySnapshot)
        .where(DailySnapshot.user_id == user.id, DailySnapshot.day >= since)
        .order_by(DailySnapshot.day.desc())
    ).all()
    return [{"day": s.day.isoformat(), "data": s.data} for s in rows]

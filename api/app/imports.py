"""File imports: CSV and Apple Health.

Health Connect has no export file — the Android client reads the SDK and POSTs points to
`/metrics`, which is the same shape this module produces. ponytail: no third endpoint.
"""

import csv
import io
import logging
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .auth import current_user
from .db import get_db
from .metrics import MetricIn, upsert
from .models import User

log = logging.getLogger("nexuscoach.imports")
router = APIRouter(prefix="/imports", tags=["imports"])

# Apple types kept at full resolution: a handful of readings per day.
APPLE_POINT_TYPES = {
    "HKQuantityTypeIdentifierBodyMass": ("weight", "kg"),
    "HKQuantityTypeIdentifierBodyFatPercentage": ("fat_ratio", "%"),
    "HKQuantityTypeIdentifierLeanBodyMass": ("fat_free_mass", "kg"),
    "HKQuantityTypeIdentifierBodyMassIndex": ("bmi", ""),
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", "bpm"),
    "HKQuantityTypeIdentifierVO2Max": ("vo2max", "ml/kg/min"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv", "ms"),
}

# Apple types rolled up to one value per day. A year of raw heart-rate samples is
# hundreds of thousands of rows; the analytics only ever read the daily figure.
APPLE_DAILY_TYPES = {
    "HKQuantityTypeIdentifierStepCount": ("steps", "count", "sum"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_kcal", "kcal", "sum"),
    "HKQuantityTypeIdentifierBasalEnergyBurned": ("basal_kcal", "kcal", "sum"),
    "HKQuantityTypeIdentifierDietaryEnergyConsumed": ("kcal_in", "kcal", "sum"),
    "HKQuantityTypeIdentifierDietaryProtein": ("protein_g", "g", "sum"),
    "HKQuantityTypeIdentifierDietaryCarbohydrates": ("carbs_g", "g", "sum"),
    "HKQuantityTypeIdentifierDietaryFatTotal": ("fat_g", "g", "sum"),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": ("distance_km", "km", "sum"),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("exercise_min", "min", "sum"),
    "HKQuantityTypeIdentifierHeartRate": ("heart_rate", "bpm", "mean"),
    "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", "%", "mean"),
}


def _bad(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message)


def _as_percent(metric: str, value: float) -> float:
    """Apple writes percentages as fractions (0.221 = 22.1 %); Withings writes 22.1."""
    if metric in ("fat_ratio", "spo2") and 0 < value <= 1:
        return value * 100
    return value


def parse_csv(text: str) -> list[MetricIn]:
    """Columns: ts, metric, value, unit — plus an optional source."""
    reader = csv.DictReader(io.StringIO(text))
    missing = {"ts", "metric", "value", "unit"} - set(reader.fieldnames or [])
    if missing:
        raise _bad(f"CSV is missing column(s): {', '.join(sorted(missing))}")

    points = []
    for line, row in enumerate(reader, start=2):
        try:
            points.append(
                MetricIn(
                    ts=datetime.fromisoformat(row["ts"]),
                    metric=row["metric"].strip(),
                    value=float(row["value"]),
                    unit=row["unit"].strip(),
                    source=(row.get("source") or "csv").strip(),
                )
            )
        except (ValueError, TypeError, KeyError) as e:
            raise _bad(f"Row {line}: {e}")
    return points


def parse_apple_health(stream) -> list[MetricIn]:
    """Stream export.xml. Never holds more than the daily buckets in memory."""
    points: list[MetricIn] = []
    daily: dict[tuple[str, str, str, datetime], list[float]] = {}

    try:
        for _, elem in ElementTree.iterparse(stream, events=("end",)):
            if elem.tag != "Record":
                continue
            kind = elem.get("type")
            point, rollup = APPLE_POINT_TYPES.get(kind), APPLE_DAILY_TYPES.get(kind)
            if point or rollup:
                try:
                    ts = datetime.strptime(elem.get("startDate"), "%Y-%m-%d %H:%M:%S %z")
                    value = float(elem.get("value"))
                except (TypeError, ValueError):
                    elem.clear()
                    continue  # Apple writes non-numeric values for some records

                if point:
                    name, unit = point
                    points.append(
                        MetricIn(
                            ts=ts,
                            metric=name,
                            value=_as_percent(name, value),
                            unit=unit,
                            source="apple_health",
                        )
                    )
                else:
                    day = ts.astimezone(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    daily.setdefault((*rollup, day), []).append(value)
            elem.clear()
    except ElementTree.ParseError as e:
        raise _bad(f"Not a valid Apple Health export: {e}")

    for (name, unit, how, day), values in daily.items():
        rolled = sum(values) / len(values) if how == "mean" else sum(values)
        points.append(
            MetricIn(
                ts=day,
                metric=name,
                value=_as_percent(name, rolled),
                unit=unit,
                source="apple_health",
            )
        )
    return points


@router.post("/csv", status_code=201)
def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        text = file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _bad("File is not UTF-8 text")
    result = upsert(db, user.id, parse_csv(text))
    log.info("csv import user_id=%s %s", user.id, result)
    return result


@router.post("/apple-health", status_code=201)
def import_apple_health(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Takes export.xml, or the export.zip Apple's Health app actually hands you."""
    stream = file.file
    if zipfile.is_zipfile(stream):
        archive = zipfile.ZipFile(stream)
        name = next((n for n in archive.namelist() if n.endswith("export.xml")), None)
        if name is None:
            raise _bad("Zip does not contain export.xml")
        stream = archive.open(name)
    else:
        stream.seek(0)

    result = upsert(db, user.id, parse_apple_health(stream))
    log.info("apple health import user_id=%s %s", user.id, result)
    return result

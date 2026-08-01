from datetime import datetime, timedelta, timezone

import pytest

from app.analytics import ema, trend
from app.models import utcnow


def seed(client, headers, metric, values, unit="kg", start_days_ago=None):
    """Writes one reading per day, oldest first, ending today."""
    start_days_ago = start_days_ago if start_days_ago is not None else len(values)
    base = utcnow() - timedelta(days=start_days_ago)
    points = [
        {
            "ts": (base + timedelta(days=i)).isoformat(),
            "metric": metric,
            "value": v,
            "unit": unit,
            "source": "test",
        }
        for i, v in enumerate(values)
    ]
    assert client.post("/metrics", json=points, headers=headers).status_code == 201


def days(n):
    return [datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(n)]


def test_ema_smooths_noise_and_tracks_the_level():
    noisy = list(zip(days(40), [80 + (1 if i % 2 else -1) for i in range(40)]))
    smoothed = [v for _, v in ema(noisy)]
    assert 79.5 < smoothed[-1] < 80.5
    # Smoothed line swings far less than the raw one.
    assert max(smoothed[10:]) - min(smoothed[10:]) < 1.0


def test_ema_decays_over_a_gap():
    """A reading after a long gap should dominate; one the next day should not."""
    near = ema([(days(1)[0], 80.0), (days(1)[0] + timedelta(days=1), 90.0)])[-1][1]
    far = ema([(days(1)[0], 80.0), (days(1)[0] + timedelta(days=60), 90.0)])[-1][1]
    assert near < far < 90


def test_trend_reports_slope_per_week():
    losing = list(zip(days(28), [85 - 0.1 * i for i in range(28)]))
    t = trend(losing)
    assert t["per_week"] == pytest.approx(-0.7, abs=0.01)
    assert t["r_squared"] > 0.99


def test_trend_is_none_without_enough_data():
    assert trend([]) is None
    assert trend(list(zip(days(2), [80, 81]))) is None
    assert trend(list(zip(days(5), [80] * 5))) is None  # flat: no spread to fit


def test_summary_separates_facts_from_analysis(client, user_token):
    seed(client, user_token, "weight", [85 - 0.1 * i for i in range(30)])
    body = client.get("/analytics/summary", headers=user_token).json()

    assert body["facts"]["weight"]["latest"] == pytest.approx(82.1)
    assert body["facts"]["weight"]["days_of_data"] == 30
    assert body["analysis"]["weight"]["trend"]["per_week"] == pytest.approx(-0.7, abs=0.05)
    # Internal regression state never leaks to the client.
    assert not any(k.startswith("_") for k in body["analysis"]["weight"]["trend"])


def test_series_returns_raw_and_smoothed(client, user_token):
    seed(client, user_token, "weight", [80.0, 82.0, 80.0, 82.0, 80.0, 82.0, 80.0])
    body = client.get("/analytics/series?metric=weight", headers=user_token).json()
    assert len(body["facts"]) == 7
    assert [p["value"] for p in body["facts"]] == [80, 82, 80, 82, 80, 82, 80]
    assert 80 < body["analysis"]["smoothed"][-1]["value"] < 82


def test_multiple_readings_in_a_day_collapse(client, user_token):
    now = utcnow().replace(hour=6, minute=0, second=0, microsecond=0)
    points = [
        {"ts": now.isoformat(), "metric": "weight", "value": 80.0, "unit": "kg", "source": "a"},
        {"ts": (now + timedelta(hours=8)).isoformat(), "metric": "weight", "value": 82.0, "unit": "kg", "source": "b"},
        {"ts": now.isoformat(), "metric": "steps", "value": 4000, "unit": "count", "source": "a"},
        {"ts": (now + timedelta(hours=8)).isoformat(), "metric": "steps", "value": 6000, "unit": "count", "source": "b"},
    ]
    client.post("/metrics", json=points, headers=user_token)
    body = client.get("/analytics/summary", headers=user_token).json()
    assert body["facts"]["weight"]["latest"] == 81.0  # averaged
    assert body["facts"]["steps"]["latest"] == 10000  # summed


def test_prediction_states_its_assumption(client, user_token):
    seed(client, user_token, "weight", [85 - 0.1 * i for i in range(30)])
    body = client.get("/analytics/predict?metric=weight&goal=80&days_ahead=14", headers=user_token).json()
    p = body["prediction"]

    assert p["available"] is True
    assert p["assumption"] == "current rate of change continues unchanged"
    # Losing 0.7 kg/week from ~82.1: 14 days ≈ -1.4 kg, and 80 kg is ~3 weeks out.
    assert p["value_in_days"]["value"] == pytest.approx(80.7, abs=0.2)
    assert p["goal"]["reachable"] is True and 15 < p["goal"]["days"] < 30


def test_unreachable_goal_is_reported_not_guessed(client, user_token):
    seed(client, user_token, "weight", [80 + 0.1 * i for i in range(30)])  # gaining
    p = client.get("/analytics/predict?metric=weight&goal=75", headers=user_token).json()["prediction"]
    assert p["goal"]["reachable"] is False


def test_prediction_without_data_is_honest(client, user_token):
    p = client.get("/analytics/predict?metric=weight&days_ahead=7", headers=user_token).json()["prediction"]
    assert p["available"] is False
    assert client.get("/analytics/predict?metric=weight", headers=user_token).status_code == 400


def test_snapshot_is_idempotent_and_computes_energy_balance(client, user_token):
    now = utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    points = [
        {"ts": now.isoformat(), "metric": m, "value": v, "unit": "kcal", "source": "test"}
        for m, v in (("kcal_in", 2400), ("active_kcal", 600), ("basal_kcal", 1700))
    ]
    client.post("/metrics", json=points, headers=user_token)

    first = client.post("/analytics/snapshot", headers=user_token).json()
    assert first["data"]["energy_balance"] == 100.0

    client.post("/analytics/snapshot", headers=user_token)
    rows = client.get("/analytics/snapshots", headers=user_token).json()
    assert len(rows) == 1  # re-running replaces, never appends


def test_analytics_are_scoped_to_the_caller(client, user_token):
    seed(client, user_token, "weight", [85 - 0.1 * i for i in range(30)])
    client.post("/auth/register", json={"email": "nosy@example.com", "password": "long-enough-pw"})
    r = client.post("/auth/login", data={"username": "nosy@example.com", "password": "long-enough-pw"})
    nosy = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/analytics/summary", headers=nosy).json() == {"facts": {}, "analysis": {}}
    assert client.get("/analytics/summary").status_code == 401

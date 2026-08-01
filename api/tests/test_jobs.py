from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import coach, jobs
from app.db import SessionLocal
from app.models import JobRun, ProviderConnection, User, utcnow


def test_seconds_until_is_always_the_next_occurrence():
    at_two = datetime(2026, 8, 1, 2, 0, tzinfo=timezone.utc)
    assert jobs.seconds_until(3, at_two) == 3600

    at_four = datetime(2026, 8, 1, 4, 0, tzinfo=timezone.utc)
    assert jobs.seconds_until(3, at_four) == 23 * 3600  # tomorrow, not the past

    exactly_three = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
    assert jobs.seconds_until(3, exactly_three) == 24 * 3600  # never fires twice


def test_run_is_claimed_once_per_day(client, user_token):
    day = utcnow().date() - timedelta(days=3)

    first = jobs.run_nightly(day)
    assert first.get("skipped") is not True

    second = jobs.run_nightly(day)
    assert second == {"skipped": True, "day": day.isoformat()}

    with SessionLocal() as db:
        runs = db.scalars(select(JobRun).where(JobRun.day == day)).all()
    assert len(runs) == 1 and runs[0].finished_at is not None


def test_force_reruns_the_same_day(client, user_token):
    day = utcnow().date() - timedelta(days=4)
    jobs.run_nightly(day)
    again = jobs.run_nightly(day, force=True)
    assert again.get("skipped") is not True


def test_one_users_failure_does_not_stop_the_batch(client, user_token, monkeypatch):
    """A provider outage for one account must not cost everyone else their sync."""
    day = utcnow().date() - timedelta(days=5)

    with SessionLocal() as db:
        users = db.scalars(select(User)).all()
        assert len(users) >= 2
        broken = users[0]
        db.add(
            ProviderConnection(
                user_id=broken.id,
                provider="withings",
                provider_user_id="1",
                access="a",
                refresh="b",
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        db.commit()
        broken_id = broken.id

    def explode(db, conn):
        raise RuntimeError("withings is down")

    monkeypatch.setattr(jobs, "sync_connection", explode)

    result = jobs.run_nightly(day)
    # The failure is recorded against that user, and everyone else still gets synced.
    assert "withings is down" in result["errors"][str(broken_id)]
    assert result["ok"] >= 1
    assert result["ok"] + result["failed"] == len(users)


def test_nightly_builds_snapshots_and_refreshes_insights(client, user_token, monkeypatch):
    # Through today, not up to yesterday — the job snapshots today.
    base = utcnow() - timedelta(days=9)
    client.post(
        "/metrics",
        json=[
            {
                "ts": (base + timedelta(days=i)).isoformat(),
                "metric": "weight",
                "value": 84 - 0.1 * i,
                "unit": "kg",
                "source": "test",
            }
            for i in range(10)
        ],
        headers=user_token,
    )
    client.put("/settings/openrouter_api_key", json={"value": "k"}, headers=user_token)
    monkeypatch.setattr(coach, "chat", lambda messages, api_key, model: "Nightly briefing.")
    monkeypatch.setattr(jobs, "chat", lambda messages, api_key, model: "Nightly briefing.")

    jobs.run_nightly(utcnow().date() - timedelta(days=6))

    snapshots = client.get("/analytics/snapshots", headers=user_token).json()
    assert snapshots[0]["data"]["metrics"]["weight"]
    assert snapshots[0]["data"]["insight"] == "Nightly briefing."


def test_users_without_a_key_cost_nothing(client, user_token, monkeypatch):
    """No API key means no insight for that user — and so no tokens spent."""
    from app.config import settings

    monkeypatch.setattr(jobs, "chat", lambda messages, api_key, model: "should not happen")
    client.delete("/settings/openrouter_api_key", headers=user_token)
    settings.openrouter_api_key = ""

    client.post(
        "/metrics",
        json=[
            {
                "ts": utcnow().isoformat(),
                "metric": "weight",
                "value": 80,
                "unit": "kg",
                "source": "test",
            }
        ],
        headers=user_token,
    )
    jobs.run_nightly(utcnow().date() - timedelta(days=7))

    snapshot = client.get("/analytics/snapshots", headers=user_token).json()[0]
    assert snapshot["data"]["metrics"]  # the snapshot was still built
    assert "insight" not in snapshot["data"]  # but the model was never called


def test_admin_only(client, user_token):
    assert client.get("/admin/jobs", headers=user_token).status_code == 403
    assert client.post("/admin/jobs/nightly", headers=user_token).status_code == 403
    assert client.get("/admin/jobs").status_code == 401


def test_tokens_are_encrypted_at_rest(client, user_token):
    """The connection stores ciphertext; the accessors hand back the real token."""
    with SessionLocal() as db:
        user = db.scalars(select(User)).first()
        conn = ProviderConnection(
            user_id=user.id,
            provider="fitbit",
            provider_user_id="9",
            access="plain-access-token",
            refresh="plain-refresh-token",
            expires_at=utcnow() + timedelta(hours=1),
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)

        assert "plain-access-token" not in conn.access_token
        assert conn.access == "plain-access-token"
        assert conn.refresh == "plain-refresh-token"



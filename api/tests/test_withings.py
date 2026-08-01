"""Withings flow with the network stubbed at `withings.call`.

Nothing here can prove Withings' real payloads — that needs a credentialed smoke test.
What it does prove: state handling, token refresh, unit scaling, and idempotent sync.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app import withings
from app.config import settings
from app.db import SessionLocal
from app.models import ProviderConnection, User, utcnow

TOKENS = {
    "userid": 4242,
    "access_token": "at-1",
    "refresh_token": "rt-1",
    "expires_in": 10800,
}
# 81.4 kg and 22.1 % body fat, in Withings' value/unit encoding.
MEASURES = {
    "updatetime": 1785000000,
    "measuregrps": [
        {
            "grpid": 1,
            "date": 1784900000,
            "measures": [
                {"value": 81400, "type": 1, "unit": -3},
                {"value": 221, "type": 6, "unit": -1},
                {"value": 999, "type": 999, "unit": 0},  # unknown type: ignored
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def credentials():
    settings.withings_client_id = "cid"
    settings.withings_client_secret = "secret"


@pytest.fixture
def calls(monkeypatch):
    """Records every Withings call and replies from the canned payloads."""
    recorded = []

    def fake_call(path, data, token=None):
        recorded.append({"path": path, "data": data, "token": token})
        if path == "/v2/oauth2":
            return {**TOKENS, "access_token": f"at-{len(recorded)}"}
        return MEASURES

    monkeypatch.setattr(withings, "call", fake_call)
    return recorded


def connect(client, headers, calls):
    state = client.get("/integrations/withings/connect", headers=headers).json()["authorize_url"]
    state = state.split("state=")[1]
    r = client.get(f"/integrations/withings/callback?code=abc&state={state}")
    assert r.status_code == 200, r.text
    return r


def test_connect_returns_authorize_url(client, user_token):
    url = client.get("/integrations/withings/connect", headers=user_token).json()["authorize_url"]
    assert url.startswith("https://account.withings.com/oauth2_user/authorize2?")
    assert "response_type=code" in url and "client_id=cid" in url


def test_callback_rejects_forged_state(client, calls):
    r = client.get("/integrations/withings/callback?code=abc&state=not-a-jwt")
    assert r.status_code == 400
    assert calls == []  # no token exchange attempted


def test_sync_normalizes_measures(client, user_token, calls):
    connect(client, user_token, calls)
    r = client.post("/integrations/withings/sync", headers=user_token)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2  # the unknown meastype was dropped

    points = {p["metric"]: p["value"] for p in client.get("/metrics", headers=user_token).json()}
    assert points == {"weight": pytest.approx(81.4), "fat_ratio": pytest.approx(22.1)}


def test_second_sync_is_incremental_and_idempotent(client, user_token, calls):
    connect(client, user_token, calls)
    client.post("/integrations/withings/sync", headers=user_token)
    r = client.post("/integrations/withings/sync", headers=user_token)

    assert r.json() == {"received": 2, "created": 0, "updated": 2}
    # First sync backfills, the second asks only for what changed.
    measure_calls = [c for c in calls if c["path"] == "/measure"]
    assert "startdate" in measure_calls[0]["data"]
    assert measure_calls[1]["data"]["lastupdate"] == MEASURES["updatetime"]


def test_expired_token_is_refreshed_before_use(client, user_token, calls):
    connect(client, user_token, calls)
    with SessionLocal() as db:
        conn = db.scalars(select(ProviderConnection)).all()[-1]
        conn.expires_at = utcnow() - timedelta(hours=1)
        db.commit()
        stale = conn.access_token

    client.post("/integrations/withings/sync", headers=user_token)
    refreshes = [c for c in calls if c["data"].get("grant_type") == "refresh_token"]
    assert len(refreshes) == 1
    assert calls[-1]["token"] != stale


def test_sync_without_connection_is_404(client, user_token, calls):
    assert client.post("/integrations/withings/sync", headers=user_token).status_code == 404


def test_disconnect_removes_only_the_callers_connection(client, user_token, calls):
    connect(client, user_token, calls)
    with SessionLocal() as db:
        before = len(db.scalars(select(ProviderConnection)).all())
        other = User(email="other@example.com", password_hash="x", role="user")
        db.add(other)
        db.commit()
        db.add(
            ProviderConnection(
                user_id=other.id,
                provider="withings",
                provider_user_id="9",
                access_token="a",
                refresh_token="b",
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        db.commit()

    assert client.delete("/integrations/withings").status_code == 401
    assert client.delete("/integrations/withings", headers=user_token).status_code == 204
    with SessionLocal() as db:
        assert len(db.scalars(select(ProviderConnection)).all()) == before

import pytest

from app import security


@pytest.fixture(autouse=True)
def clean_counters():
    security.reset()
    yield
    security.reset()


def test_login_attempts_are_capped_per_ip(client):
    bad = {"username": "nobody@example.com", "password": "wrong-password"}
    codes = [client.post("/auth/login", data=bad).status_code for _ in range(16)]

    assert codes[:15] == [401] * 15  # the limit is 15 in 5 minutes
    assert codes[15] == 429


def test_the_limit_response_says_when_to_retry(client):
    bad = {"username": "nobody@example.com", "password": "wrong-password"}
    for _ in range(15):
        client.post("/auth/login", data=bad)

    r = client.post("/auth/login", data=bad)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    assert "Try again" in r.json()["detail"]


def test_coach_is_capped_per_user_not_per_ip(client, user_token, monkeypatch):
    """Two accounts from the same machine must not share a budget."""
    from app import coach

    monkeypatch.setattr(coach, "chat", lambda m, k, model: "ok")
    from app.config import settings

    settings.openrouter_api_key = "server-key"

    for _ in range(40):
        assert client.post("/coach/ask", json={"question": "hi"}, headers=user_token).status_code == 200
    assert client.post("/coach/ask", json={"question": "hi"}, headers=user_token).status_code == 429

    client.post("/auth/register", json={"email": "second@example.com", "password": "long-enough-pw"})
    r = client.post("/auth/login", data={"username": "second@example.com", "password": "long-enough-pw"})
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/coach/ask", json={"question": "hi"}, headers=other).status_code == 200


def test_security_headers_are_present(client):
    h = client.get("/health").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "no-referrer"
    assert "max-age=" in h["Strict-Transport-Security"]


def test_oversized_uploads_are_rejected_before_being_read(client, user_token):
    r = client.post(
        "/imports/csv",
        headers={**user_token, "Content-Length": str(security.MAX_BODY_BYTES + 1)},
        content=b"x",
    )
    assert r.status_code == 413
    assert "too large" in r.json()["detail"].lower()

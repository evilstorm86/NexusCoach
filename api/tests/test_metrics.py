POINT = {
    "ts": "2026-07-30T06:30:00+00:00",
    "metric": "weight",
    "value": 81.4,
    "unit": "kg",
    "source": "withings",
}


def test_ingest_then_read_back(client, user_token):
    r = client.post("/metrics", json=[POINT], headers=user_token)
    assert r.status_code == 201, r.text
    assert r.json() == {"received": 1, "created": 1, "updated": 0}

    body = client.get("/metrics", headers=user_token).json()
    assert len(body) == 1
    assert body[0]["value"] == 81.4 and body[0]["metric"] == "weight"


def test_resync_updates_instead_of_duplicating(client, user_token):
    client.post("/metrics", json=[POINT], headers=user_token)
    r = client.post("/metrics", json=[{**POINT, "value": 81.9}], headers=user_token)
    assert r.json() == {"received": 1, "created": 0, "updated": 1}

    body = client.get("/metrics", headers=user_token).json()
    assert len(body) == 1 and body[0]["value"] == 81.9


def test_users_cannot_see_each_others_metrics(client, user_token):
    alice = user_token
    client.post("/metrics", json=[POINT], headers=alice)

    bob = client.post("/auth/register", json={"email": "bob@example.com", "password": "another-long-one"})
    assert bob.status_code == 201
    r = client.post("/auth/login", data={"username": "bob@example.com", "password": "another-long-one"})
    bob_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/metrics", headers=bob_headers).json() == []
    # Bob writing the same point does not touch Alice's row.
    client.post("/metrics", json=[{**POINT, "value": 60.0}], headers=bob_headers)
    assert client.get("/metrics", headers=alice).json()[0]["value"] == 81.4


def test_filters_and_auth(client, user_token):
    client.post("/metrics", json=[POINT], headers=user_token)
    assert client.get("/metrics?metric=steps", headers=user_token).json() == []
    assert client.get("/metrics?since=2026-08-01T00:00:00Z", headers=user_token).json() == []
    assert client.get("/metrics").status_code == 401

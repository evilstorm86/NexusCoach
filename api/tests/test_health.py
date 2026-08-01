def test_health_reports_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert "scheduler" in body  # so "why did the nightly job not run" is answerable

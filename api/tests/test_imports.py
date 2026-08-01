import io
import zipfile

import pytest

CSV = (
    "ts,metric,value,unit\n"
    "2026-07-30T06:30:00+00:00,weight,81.4,kg\n"
    "2026-07-31T06:30:00+00:00,weight,81.1,kg\n"
)

APPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_GB">
  <Record type="HKQuantityTypeIdentifierBodyMass" unit="kg"
          startDate="2026-07-30 06:30:00 +0000" value="81.4"/>
  <Record type="HKQuantityTypeIdentifierBodyFatPercentage" unit="%"
          startDate="2026-07-30 06:30:00 +0000" value="0.221"/>
  <Record type="HKQuantityTypeIdentifierStepCount" unit="count"
          startDate="2026-07-30 09:00:00 +0000" value="1200"/>
  <Record type="HKQuantityTypeIdentifierStepCount" unit="count"
          startDate="2026-07-30 18:00:00 +0000" value="3400"/>
  <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min"
          startDate="2026-07-30 09:00:00 +0000" value="60"/>
  <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min"
          startDate="2026-07-30 09:01:00 +0000" value="80"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisAsleep"
          startDate="2026-07-30 23:00:00 +0000"/>
  <Record type="HKQuantityTypeIdentifierBodyMass" unit="kg"
          startDate="2026-07-31 06:30:00 +0000" value="not-a-number"/>
</HealthData>
"""


def post_file(client, headers, path, name, data):
    return client.post(path, files={"file": (name, data)}, headers=headers)


def metrics(client, headers):
    return {p["metric"]: p["value"] for p in client.get("/metrics", headers=headers).json()}


def test_csv_import(client, user_token):
    r = post_file(client, user_token, "/imports/csv", "m.csv", CSV.encode())
    assert r.status_code == 201, r.text
    assert r.json() == {"received": 2, "created": 2, "updated": 0}
    weights = [p["value"] for p in client.get("/metrics", headers=user_token).json()]
    assert weights == [81.1, 81.4]  # newest first


def test_csv_reimport_is_idempotent(client, user_token):
    post_file(client, user_token, "/imports/csv", "m.csv", CSV.encode())
    r = post_file(client, user_token, "/imports/csv", "m.csv", CSV.encode())
    assert r.json() == {"received": 2, "created": 0, "updated": 2}


def test_csv_rejects_missing_column_and_bad_row(client, user_token):
    r = post_file(client, user_token, "/imports/csv", "m.csv", b"ts,metric,value\n2026-01-01,x,1\n")
    assert r.status_code == 422 and "unit" in r.json()["detail"]

    bad = "ts,metric,value,unit\n2026-07-30T06:30:00+00:00,weight,heavy,kg\n"
    r = post_file(client, user_token, "/imports/csv", "m.csv", bad.encode())
    assert r.status_code == 422 and "Row 2" in r.json()["detail"]


def test_apple_health_xml(client, user_token):
    r = post_file(client, user_token, "/imports/apple-health", "export.xml", APPLE_XML.encode())
    assert r.status_code == 201, r.text

    got = metrics(client, user_token)
    assert got["weight"] == 81.4
    assert got["fat_ratio"] == pytest.approx(22.1)  # fraction converted to percent
    assert got["steps"] == 4600  # summed over the day
    assert got["heart_rate"] == 70  # averaged over the day
    assert "sleep" not in got  # non-numeric category records are skipped
    assert len(client.get("/metrics", headers=user_token).json()) == 4  # bad row dropped


def test_apple_health_zip(client, user_token):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("apple_health_export/export.xml", APPLE_XML)
    r = post_file(client, user_token, "/imports/apple-health", "export.zip", buf.getvalue())
    assert r.status_code == 201, r.text
    assert metrics(client, user_token)["steps"] == 4600


def test_apple_health_rejects_garbage(client, user_token):
    r = post_file(client, user_token, "/imports/apple-health", "export.xml", b"<not xml")
    assert r.status_code == 422


def test_imports_require_auth(client):
    assert post_file(client, {}, "/imports/csv", "m.csv", CSV.encode()).status_code == 401

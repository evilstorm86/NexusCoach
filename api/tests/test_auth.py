from sqlalchemy import select

from app.db import SessionLocal
from app.models import User

CREDS = {"username": "athlete@example.com", "password": "correct-horse-battery"}


def register(client, email, password="correct-horse-battery"):
    return client.post("/auth/register", json={"email": email, "password": password})


def token(client, username=CREDS["username"], password=CREDS["password"]):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_register_login_me(client):
    r = register(client, CREDS["username"])
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "user"
    assert "password" not in r.text

    r = client.get("/auth/me", headers=auth(token(client)))
    assert r.json()["email"] == CREDS["username"]


def test_password_is_hashed(client):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == CREDS["username"]))
    assert user.password_hash.startswith("$2b$")
    assert CREDS["password"] not in user.password_hash


def test_duplicate_email_rejected(client):
    assert register(client, CREDS["username"]).status_code == 409
    assert register(client, "ATHLETE@example.com").status_code == 409  # case-insensitive


def test_short_password_rejected(client):
    assert register(client, "weak@example.com", "short").status_code == 422


def test_wrong_password_rejected(client):
    r = client.post("/auth/login", data={**CREDS, "password": "nope"})
    assert r.status_code == 401


def test_bad_and_missing_token_rejected(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth("garbage")).status_code == 401


def test_role_guard(client):
    register(client, "coach@example.com")
    plain = token(client)
    assert client.get("/admin/ping", headers=auth(plain)).status_code == 403

    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == "coach@example.com")).role = "admin"
        db.commit()
    assert client.get("/admin/ping", headers=auth(token(client, "coach@example.com"))).status_code == 200

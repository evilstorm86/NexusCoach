import os
import pathlib

# ponytail: sqlite file instead of a throwaway postgres. Nothing here is postgres-specific yet.
DB_FILE = pathlib.Path(__file__).parent / "test.db"
DB_FILE.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_FILE}"
os.environ["JWT_SECRET"] = "test-secret"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import security  # noqa: E402
from app.main import app  # noqa: E402

API_DIR = pathlib.Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nothing in the suite may talk to the internet.

    The nightly job iterates every user, and users created by earlier tests have real
    stored API keys — without this, running the job in a test dials OpenRouter for
    real. Tests that exercise these paths re-patch them with their own stub.
    """

    def blocked(*args, **kwargs):
        raise AssertionError("test attempted a real network call")

    monkeypatch.setattr("app.coach.chat", blocked)
    monkeypatch.setattr("app.jobs.chat", blocked)
    monkeypatch.setattr("app.withings.call", blocked)
    monkeypatch.setattr("app.jobs.sync_connection", blocked)


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Every test gets its own budget.

    The limiter keys on client IP, and the whole suite shares one — without this, tests
    fail in whatever order happens to exhaust the login limit first.
    """
    security.reset()


@pytest.fixture(scope="session")
def client():
    # Tests run the real migrations, so a broken migration fails the suite.
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    command.upgrade(cfg, "head")
    yield TestClient(app)
    DB_FILE.unlink(missing_ok=True)


@pytest.fixture
def user_token(client):
    """Registers a fresh user and returns its bearer header."""
    counter = user_token.counter = getattr(user_token, "counter", 0) + 1
    email, password = f"u{counter}@example.com", "correct-horse-battery"
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

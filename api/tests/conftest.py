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

from app.main import app  # noqa: E402

API_DIR = pathlib.Path(__file__).parent.parent


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

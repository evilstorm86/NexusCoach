import os
import pathlib

# ponytail: sqlite file instead of a throwaway postgres. Nothing here is postgres-specific yet.
DB_FILE = pathlib.Path(__file__).parent / "test.db"
DB_FILE.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_FILE}"
os.environ["JWT_SECRET"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # triggers lifespan -> create_all
        yield c
    DB_FILE.unlink(missing_ok=True)

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from . import db
from .auth import require_role, router as auth_router
from .models import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: create_all until milestone 3 brings alembic. Fine while there are no migrations to run.
    db.Base.metadata.create_all(db.engine)
    yield


app = FastAPI(title="NexusCoach API", lifespan=lifespan)
app.include_router(auth_router)


@app.get("/health")
def health():
    try:
        database = "up" if db.ping() else "down"
    except Exception:
        database = "down"
    return {"status": "ok", "database": database}


@app.get("/admin/ping")
def admin_ping(user: User = Depends(require_role("admin"))):
    return {"ok": True, "user_id": user.id}

import logging

from fastapi import Depends, FastAPI

from . import db
from .auth import require_role, router as auth_router
from .imports import router as imports_router
from .metrics import router as metrics_router
from .models import User
from .withings import router as withings_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Schema is created by `alembic upgrade head` (run by the api container on start).
app = FastAPI(title="NexusCoach API")
app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(imports_router)
app.include_router(withings_router)


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

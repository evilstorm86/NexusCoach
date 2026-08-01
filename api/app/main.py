import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .auth import require_role, router as auth_router
from .analytics import router as analytics_router
from .coach import router as coach_router
from .imports import router as imports_router
from .jobs import router as jobs_router, scheduler
from .metrics import router as metrics_router
from .models import User
from .security import BodySizeLimit, SecurityHeaders
from .user_settings import router as settings_router
from .withings import router as withings_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("nexuscoach")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.run_scheduler:
        task = asyncio.create_task(scheduler())
        log.info("nightly scheduler on, %02d:00 UTC", settings.nightly_hour)
    yield
    if task:
        task.cancel()


# Schema is created by `alembic upgrade head` (run by the api container on start).
app = FastAPI(title="NexusCoach API", lifespan=lifespan)

app.add_middleware(SecurityHeaders)
app.add_middleware(BodySizeLimit)

# The PWA is served from a different origin than the API, so the browser needs this.
# Explicit list, never "*": credentials-bearing requests deserve a named origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(analytics_router)
app.include_router(coach_router)
app.include_router(imports_router)
app.include_router(jobs_router)
app.include_router(settings_router)
app.include_router(withings_router)


@app.get("/health")
def health():
    try:
        database = "up" if db.ping() else "down"
    except Exception:
        database = "down"
    return {"status": "ok", "database": database, "scheduler": settings.run_scheduler}


@app.get("/admin/ping")
def admin_ping(user: User = Depends(require_role("admin"))):
    return {"ok": True, "user_id": user.id}

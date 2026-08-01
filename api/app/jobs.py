"""Nightly synchronisation (spec §7).

Per user, in order: refresh provider tokens and pull new measures, rebuild today's
snapshot, then refresh the AI insight. One user's failure never stops the batch — a
Withings outage or a bad API key should cost that user their sync, not everyone's.

ponytail: an asyncio task in the API process, not Celery or a separate worker. There is
one job, once a night, on a 2 vCPU box. The `job_runs` unique key makes it safe to run
more than one instance — the loser of the insert simply skips. Ceiling: if the work ever
needs to outlive a deploy or fan out, that's when a real queue earns its keep.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import user_settings
from .analytics import build_snapshot
from .auth import require_role
from .coach import INSIGHT_PROMPT, build_context, chat, messages_for
from .config import settings
from .db import SessionLocal, get_db
from .models import JobRun, ProviderConnection, User, utcnow
from .withings import sync_connection

log = logging.getLogger("nexuscoach.jobs")
router = APIRouter(prefix="/admin/jobs", tags=["admin"])

NIGHTLY = "nightly"


def seconds_until(hour: int, now: datetime | None = None) -> float:
    """Seconds until the next occurrence of `hour`:00 UTC."""
    now = now or utcnow()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def sync_user(db: Session, user: User) -> dict:
    """Everything tonight does for one user. Raises on failure — the caller records it."""
    result: dict = {"user_id": user.id}

    connections = db.scalars(
        select(ProviderConnection).where(ProviderConnection.user_id == user.id)
    ).all()
    for conn in connections:
        # sync_connection refreshes the token first if it is close to expiring.
        result[conn.provider] = sync_connection(db, conn)

    snapshot = build_snapshot(db, user.id)
    result["snapshot_metrics"] = len(snapshot.data.get("metrics", {}))

    # Only users with a key and some data get an insight — no key, no spend.
    if user_settings.get(db, user.id, "openrouter_api_key"):
        context = build_context(db, user)
        if context["has_data"]:
            key, model = (
                user_settings.get(db, user.id, "openrouter_api_key"),
                user_settings.get(db, user.id, "openrouter_model"),
            )
            snapshot.data = {
                **snapshot.data,
                "insight": chat(messages_for(context, INSIGHT_PROMPT), key, model),
            }
            db.commit()
            result["insight"] = True
    return result


def run_nightly(day: date | None = None, force: bool = False) -> dict:
    """Claim tonight's run and process every user. Safe to call twice — the second
    call finds the row already there and skips."""
    day = day or utcnow().date()

    with SessionLocal() as db:
        run = JobRun(name=NIGHTLY, day=day)
        db.add(run)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not force:
                log.info("nightly already ran for %s — skipping", day)
                return {"skipped": True, "day": day.isoformat()}
            run = db.scalar(select(JobRun).where(JobRun.name == NIGHTLY, JobRun.day == day))
            run.started_at = utcnow()

        user_ids = list(db.scalars(select(User.id)))

    ok, failed, errors = 0, 0, {}
    for user_id in user_ids:
        # A session per user, so one rollback can't poison the next.
        with SessionLocal() as db:
            user = db.get(User, user_id)
            try:
                sync_user(db, user)
                ok += 1
            except Exception as e:
                db.rollback()
                failed += 1
                errors[str(user_id)] = f"{type(e).__name__}: {e}"[:200]
                log.warning("nightly failed user_id=%s: %s", user_id, e)

    with SessionLocal() as db:
        run = db.scalar(select(JobRun).where(JobRun.name == NIGHTLY, JobRun.day == day))
        run.finished_at = utcnow()
        run.ok, run.failed, run.detail = ok, failed, {"errors": errors}
        db.commit()

    log.info("nightly done day=%s ok=%s failed=%s", day, ok, failed)
    return {"day": day.isoformat(), "ok": ok, "failed": failed, "errors": errors}


async def scheduler() -> None:
    """Sleep until the configured hour, run, repeat."""
    while True:
        delay = seconds_until(settings.nightly_hour)
        log.info("nightly scheduled in %.0f min", delay / 60)
        await asyncio.sleep(delay)
        try:
            # to_thread: the job is synchronous DB and HTTP work, and must not block
            # the event loop serving requests.
            await asyncio.to_thread(run_nightly)
        except Exception:
            log.exception("nightly crashed; will try again tomorrow")


@router.post("/nightly")
async def trigger(force: bool = True, _: User = Depends(require_role("admin"))):
    """Run it now. Admin only — it syncs and spends tokens for every user."""
    return await asyncio.to_thread(run_nightly, None, force)


@router.get("")
def recent(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    runs = db.scalars(select(JobRun).order_by(JobRun.day.desc()).limit(30)).all()
    return [
        {
            "name": r.name,
            "day": r.day.isoformat(),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "ok": r.ok,
            "failed": r.failed,
            "errors": (r.detail or {}).get("errors", {}),
        }
        for r in runs
    ]


def utc_now_hint() -> str:
    """Small helper for the health payload — makes 'why did it not run' answerable."""
    return datetime.now(timezone.utc).isoformat()

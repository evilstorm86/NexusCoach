"""AI coach — OpenRouter only.

The coach never sees the database. It is handed a compact JSON context built from the
same analytics the UI shows, already split into facts / analysis / prediction, and is
told to keep that separation in what it says. Two guardrails matter more than the
prompt wording:

  * it can only talk about numbers we actually measured (they are in the context), and
  * it is not a clinician — no diagnosis, no treatment, no dosages.
"""

import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import security, user_settings
from .analytics import build_snapshot, project, series, summarize
from .db import get_db
from .models import DailySnapshot, ProviderConnection, User, utcnow

log = logging.getLogger("nexuscoach.coach")
router = APIRouter(prefix="/coach", tags=["coach"])

API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are NexusCoach, a health and fitness coach for one person.

You are given a JSON context built from that person's own measurements. Everything you
say about their body, training, nutrition or recovery must come from it. If the context
does not contain what you need, say so plainly and tell them which data to connect or
upload — never invent a number, and never infer one you were not given.

Keep three kinds of statement apart, and make clear which one you are making:
  FACT       — a value that was measured. Quote it with its date.
  ANALYSIS   — what the measurements imply: a trend, a rate of change, a comparison.
  PREDICTION — an extrapolation. Always state the assumption it rests on.

You are not a clinician and this is not a medical service. Do not diagnose conditions,
interpret symptoms, or recommend treatments, medications, supplements or dosages. If
something in the data looks clinically concerning, say what you observe, say plainly
that it is outside what you can interpret, and suggest they raise it with a doctor.

Be concise and specific. Prefer one concrete, actionable suggestion over a list of
generalities. Use the units given in the context."""

INSIGHT_PROMPT = (
    "Write today's briefing in 3-5 short sentences: what changed, what it implies, "
    "and one thing to do today. Label facts, analysis and prediction as instructed."
)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # ponytail: the client resends the last few turns instead of us storing threads.
    # Add a conversations table when someone needs history across devices.
    history: list[dict] = Field(default_factory=list, max_length=20)


def credentials(db: Session, user_id: int) -> tuple[str, str]:
    """The user's own OpenRouter key and model, falling back to the server's."""
    key = user_settings.get(db, user_id, "openrouter_api_key")
    if not key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No OpenRouter API key. Add one under Profile → Settings.",
        )
    return key, user_settings.get(db, user_id, "openrouter_model")


def chat(messages: list[dict], api_key: str, model: str) -> str:
    """One OpenRouter completion. The only place this app talks to an LLM."""
    r = httpx.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "X-Title": "NexusCoach"},
        json={"model": model, "messages": messages},
        timeout=90,
    )
    if r.status_code != 200:
        log.warning("openrouter error status=%s body=%s", r.status_code, r.text[:500])
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI coach is unavailable right now")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        log.warning("openrouter unexpected payload: %s", r.text[:500])
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI coach returned an unusable response")


def build_context(db: Session, user: User) -> dict:
    """Everything the coach is allowed to know, and nothing else."""
    summary = summarize(db, user.id)
    weight = series(db, user.id, "weight", days=90)

    snapshot = db.scalar(
        select(DailySnapshot)
        .where(DailySnapshot.user_id == user.id)
        .order_by(DailySnapshot.day.desc())
    )
    sources = db.scalars(
        select(ProviderConnection.provider).where(ProviderConnection.user_id == user.id)
    ).all()

    return {
        "today": utcnow().date().isoformat(),
        "facts": summary["facts"],
        "analysis": summary["analysis"],
        "prediction": {"weight": project(weight, goal=None, days_ahead=30)},
        "latest_day": {"day": snapshot.day.isoformat(), **snapshot.data} if snapshot else None,
        "connected_sources": list(sources),
        "has_data": bool(summary["facts"]),
    }


def messages_for(context: dict, question: str, history: list[dict] | None = None) -> list[dict]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Context for this person:\n{json.dumps(context, default=str)}"},
    ]
    for turn in history or []:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:4000]})
    messages.append({"role": "user", "content": question})
    return messages


@router.post("/ask")
def ask(
    body: Ask,
    db: Session = Depends(get_db),
    # Every call spends the user's own tokens — cap the blast radius of a runaway client.
    user: User = Depends(security.by_user("coach_ask", 40, 3600)),
):
    key, model = credentials(db, user.id)
    context = build_context(db, user)
    answer = chat(messages_for(context, body.question, body.history), key, model)
    log.info("coach ask user_id=%s chars=%s", user.id, len(answer))
    return {"answer": answer, "grounded_in": sorted(context["facts"]), "model": model}


@router.post("/insight")
def insight(
    db: Session = Depends(get_db),
    user: User = Depends(security.by_user("coach_insight", 20, 3600)),
    refresh: bool = False,
):
    """Today's briefing. Cached on the daily snapshot so the nightly job can warm it."""
    key, model = credentials(db, user.id)
    snapshot = build_snapshot(db, user.id)
    cached = snapshot.data.get("insight")
    if cached and not refresh:
        return {"insight": cached, "cached": True}

    context = build_context(db, user)
    if not context["has_data"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "No data yet — connect a device or upload a file")

    text = chat(messages_for(context, INSIGHT_PROMPT), key, model)
    # `data` is a plain JSON column, so replace it rather than mutating in place.
    snapshot.data = {**snapshot.data, "insight": text}
    db.commit()
    log.info("coach insight user_id=%s", user.id)
    return {"insight": text, "cached": False}

"""Withings integration: OAuth2 web flow + measure sync.

Endpoints and the `status`-in-the-body error envelope are Withings' v2 API. There is no
HTTP status to check — a failed call still returns 200 with a non-zero `status`.
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status as http
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import user_settings
from .auth import ALGORITHM, current_user
from .config import settings
from .db import get_db
from .metrics import MetricIn, upsert
from .models import ProviderConnection, User, utcnow

log = logging.getLogger("nexuscoach.withings")
router = APIRouter(prefix="/integrations/withings", tags=["integrations"])

PROVIDER = "withings"
AUTHORIZE_URL = "https://account.withings.com/oauth2_user/authorize2"
API_URL = "https://wbsapi.withings.net"
SCOPE = "user.metrics,user.activity"

# Withings meastype -> (our metric name, unit). Anything else is ignored.
MEASTYPES = {
    1: ("weight", "kg"),
    5: ("fat_free_mass", "kg"),
    6: ("fat_ratio", "%"),
    8: ("fat_mass", "kg"),
    9: ("diastolic_bp", "mmHg"),
    10: ("systolic_bp", "mmHg"),
    11: ("heart_rate", "bpm"),
    54: ("spo2", "%"),
    71: ("body_temp", "C"),
    76: ("muscle_mass", "kg"),
    77: ("hydration", "kg"),
    88: ("bone_mass", "kg"),
}


def call(path: str, data: dict, token: str | None = None) -> dict:
    """POST to Withings and return `body`, raising on the in-band error status."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.post(f"{API_URL}{path}", data=data, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") != 0:
        log.warning("withings error path=%s payload=%s", path, payload)
        raise HTTPException(http.HTTP_502_BAD_GATEWAY, f"Withings error {payload.get('status')}")
    return payload.get("body", {})


def credentials(db: Session, user_id: int) -> tuple[str, str]:
    """This user's Withings app credentials, falling back to the deployment's own."""
    client_id = user_settings.get(db, user_id, "withings_client_id")
    client_secret = user_settings.get(db, user_id, "withings_client_secret")
    if not client_id or not client_secret:
        raise HTTPException(
            http.HTTP_503_SERVICE_UNAVAILABLE,
            "Withings is not configured. Add client credentials under Profile → Settings.",
        )
    return client_id, client_secret


def _store_tokens(db: Session, user_id: int, body: dict) -> ProviderConnection:
    conn = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.user_id == user_id, ProviderConnection.provider == PROVIDER
        )
    )
    expires_at = utcnow() + timedelta(seconds=int(body["expires_in"]))
    if conn is None:
        conn = ProviderConnection(user_id=user_id, provider=PROVIDER)
        db.add(conn)
    conn.provider_user_id = str(body.get("userid", ""))
    conn.access = body["access_token"]
    conn.refresh = body["refresh_token"]
    conn.expires_at = expires_at
    db.commit()
    db.refresh(conn)
    return conn


def fresh_token(db: Session, conn: ProviderConnection) -> str:
    """Access token, refreshed if it expires within the minute."""
    expires_at = conn.expires_at
    if expires_at.tzinfo is None:  # sqlite hands back naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > utcnow() + timedelta(seconds=60):
        return conn.access

    client_id, client_secret = credentials(db, conn.user_id)
    body = call(
        "/v2/oauth2",
        {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": conn.refresh,
        },
    )
    log.info("refreshed token user_id=%s", conn.user_id)
    return _store_tokens(db, conn.user_id, body).access


def to_points(measuregrps: list[dict]) -> list[MetricIn]:
    """Flatten Withings measure groups. Real value is `value * 10 ** unit`."""
    points = []
    for grp in measuregrps:
        ts = datetime.fromtimestamp(grp["date"], tz=timezone.utc)
        for m in grp.get("measures", []):
            known = MEASTYPES.get(m["type"])
            if known is None:
                continue
            name, unit = known
            points.append(
                MetricIn(
                    ts=ts,
                    metric=name,
                    value=m["value"] * (10 ** m["unit"]),
                    unit=unit,
                    source=PROVIDER,
                )
            )
    return points


def sync_connection(db: Session, conn: ProviderConnection) -> dict:
    """Pull everything changed since the last sync. Safe to run repeatedly."""
    token = fresh_token(db, conn)
    params = {"action": "getmeas", "meastypes": ",".join(str(t) for t in MEASTYPES), "category": 1}
    if conn.last_update:
        params["lastupdate"] = conn.last_update
    else:
        # First sync: a year of history is plenty to seed trends.
        params["startdate"] = int((utcnow() - timedelta(days=365)).timestamp())
        params["enddate"] = int(utcnow().timestamp())

    body = call("/measure", params, token)
    result = upsert(db, conn.user_id, to_points(body.get("measuregrps", [])))

    if body.get("updatetime"):
        conn.last_update = int(body["updatetime"])
        db.commit()
    log.info("sync user_id=%s %s", conn.user_id, result)
    return result


@router.get("/connect")
def connect(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """URL to send the user to. `state` is a short-lived JWT, so no server-side store."""
    client_id, _ = credentials(db, user.id)
    state = jwt.encode(
        {"sub": str(user.id), "exp": utcnow() + timedelta(minutes=10)},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "scope": SCOPE,
            "redirect_uri": settings.withings_redirect_uri,
            "state": state,
        }
    )
    return {"authorize_url": f"{AUTHORIZE_URL}?{query}"}


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    try:
        user_id = int(jwt.decode(state, settings.jwt_secret, algorithms=[ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(http.HTTP_400_BAD_REQUEST, "Invalid or expired state")

    client_id, client_secret = credentials(db, user_id)
    body = call(
        "/v2/oauth2",
        {
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": settings.withings_redirect_uri,
        },
    )
    _store_tokens(db, user_id, body)
    log.info("connected user_id=%s", user_id)
    return {"connected": True, "provider": PROVIDER}


@router.get("")
def status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Whether this user is connected, so the UI can stop offering Sync to nobody."""
    conn = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.user_id == user.id, ProviderConnection.provider == PROVIDER
        )
    )
    return {
        "connected": conn is not None,
        "configured": bool(user_settings.get(db, user.id, "withings_client_id")),
        "last_sync": (
            datetime.fromtimestamp(conn.last_update, tz=timezone.utc).isoformat()
            if conn and conn.last_update
            else None
        ),
    }


@router.post("/sync")
def sync(db: Session = Depends(get_db), user: User = Depends(current_user)):
    conn = db.scalar(
        select(ProviderConnection).where(
            ProviderConnection.user_id == user.id, ProviderConnection.provider == PROVIDER
        )
    )
    if conn is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "Withings is not connected")
    return sync_connection(db, conn)


@router.delete("", status_code=204)
def disconnect(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.query(ProviderConnection).filter_by(user_id=user.id, provider=PROVIDER).delete()
    db.commit()

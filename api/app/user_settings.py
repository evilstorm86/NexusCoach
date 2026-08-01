"""Per-user configuration: the user's own API keys and service settings.

Resolution order is always **user setting → environment default**. The env vars stay as
the deployment-wide fallback, so a single-tenant install still works with nothing
configured in the UI, and a multi-tenant one lets each user bring their own keys.
"""

import logging
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user
from .config import settings
from .crypto import decrypt, encrypt, mask
from .db import get_db
from .models import User, UserSetting

log = logging.getLogger("nexuscoach.settings")
router = APIRouter(prefix="/settings", tags=["settings"])


@dataclass(frozen=True)
class Spec:
    label: str
    help: str
    secret: bool
    env_default: str  # attribute on Settings used when the user hasn't set one


SPECS: dict[str, Spec] = {
    "openrouter_api_key": Spec(
        label="OpenRouter API key",
        help="Your own key from openrouter.ai. The AI coach bills to it.",
        secret=True,
        env_default="openrouter_api_key",
    ),
    "openrouter_model": Spec(
        label="AI model",
        help="OpenRouter model slug, e.g. anthropic/claude-opus-5.",
        secret=False,
        env_default="openrouter_model",
    ),
    "withings_client_id": Spec(
        label="Withings client ID",
        # Withings issues these per registered application, not per person — most
        # installs leave them blank and use the deployment's own app.
        help="Only if you registered your own app at developer.withings.com.",
        secret=False,
        env_default="withings_client_id",
    ),
    "withings_client_secret": Spec(
        label="Withings client secret",
        help="Goes with your own Withings client ID.",
        secret=True,
        env_default="withings_client_secret",
    ),
}


class SettingIn(BaseModel):
    value: str = Field(max_length=1024)


def _spec(name: str) -> Spec:
    spec = SPECS.get(name)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown setting: {name}")
    return spec


def get(db: Session, user_id: int, name: str) -> str:
    """The effective value for this user: their setting, else the env default."""
    spec = _spec(name)
    row = db.get(UserSetting, (user_id, name))
    if row:
        value = decrypt(row.value) if spec.secret else row.value
        if value:
            return value
    return getattr(settings, spec.env_default, "") or ""


@router.get("")
def list_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Never returns a secret — only whether one is set, and a hint of which."""
    rows = {
        r.name: r
        for r in db.scalars(select(UserSetting).where(UserSetting.user_id == user.id))
    }
    out = []
    for name, spec in SPECS.items():
        row = rows.get(name)
        stored = (decrypt(row.value) if spec.secret else row.value) if row else None
        effective = stored or getattr(settings, spec.env_default, "") or ""
        out.append(
            {
                "name": name,
                "label": spec.label,
                "help": spec.help,
                "secret": spec.secret,
                "configured": bool(effective),
                "source": "user" if stored else ("server" if effective else "unset"),
                # Secrets show a hint; plain values show the value itself.
                "value": (mask(effective) if spec.secret else effective) if effective else "",
                "updated_at": row.updated_at.isoformat() if row else None,
            }
        )
    return out


@router.put("/{name}")
def set_setting(
    name: str,
    body: SettingIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    spec = _spec(name)
    value = body.value.strip()
    if not value:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Value cannot be empty")

    row = db.get(UserSetting, (user.id, name))
    if row is None:
        row = UserSetting(user_id=user.id, name=name)
        db.add(row)
    row.value = encrypt(value) if spec.secret else value
    db.commit()
    log.info("setting updated user_id=%s name=%s", user.id, name)  # value never logged
    return {"name": name, "configured": True, "source": "user"}


@router.delete("/{name}", status_code=204)
def clear_setting(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    _spec(name)
    db.query(UserSetting).filter_by(user_id=user.id, name=name).delete()
    db.commit()
    log.info("setting cleared user_id=%s name=%s", user.id, name)

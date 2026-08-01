"""Production hardening: rate limits, security headers, upload cap.

ponytail: the rate limiter is an in-process dict of deques, not Redis. One API container
on one VM is the deployment, and a dependency that needs its own server to protect a
single process is the wrong trade. Ceiling is explicit: counters are per-process and
reset on restart, so the moment there are two replicas this moves to a shared store.
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .models import User

log = logging.getLogger("nexuscoach.security")

_hits: dict[str, deque[float]] = defaultdict(deque)

# Uploads are Apple Health exports — big, but not unbounded.
MAX_BODY_BYTES = 100 * 1024 * 1024


def _check(key: str, limit: int, window: int) -> None:
    now = time.monotonic()
    hits = _hits[key]
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
        retry = int(window - (now - hits[0])) + 1
        log.warning("rate limited key=%s", key)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many requests. Try again in {retry}s.",
            headers={"Retry-After": str(retry)},
        )
    hits.append(now)


def by_ip(name: str, limit: int, window: int):
    """For unauthenticated routes — login and register, where the risk is guessing."""

    def guard(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        _check(f"{name}:{client}", limit, window)

    return guard


def by_user(name: str, limit: int, window: int):
    """For routes that cost money or time, keyed to the account rather than the IP."""
    # Imported here, not at module scope: auth depends on this module for its own
    # login/register limits, and a top-level import would close the cycle.
    from .auth import current_user

    def guard(user: User = Depends(current_user)) -> User:
        _check(f"{name}:{user.id}", limit, window)
        return user

    return guard


def reset() -> None:
    """Test helper — the counters are process-global."""
    _hits.clear()


class SecurityHeaders(BaseHTTPMiddleware):
    """Headers that cost nothing and close the cheap holes.

    No CSP here: this app serves JSON, and the PWA is a separate origin whose CSP
    belongs with whatever serves it.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # The tunnel terminates TLS; tell browsers to keep coming back over it.
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response


class BodySizeLimit(BaseHTTPMiddleware):
    """Reject oversized uploads on the declared length, before reading the body.

    ponytail: Content-Length only. A chunked request without one still streams to the
    handler — the real backstop is a limit at the tunnel/proxy, which this complements
    rather than replaces.
    """

    async def dispatch(self, request: Request, call_next):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            return JSONResponse(
                {"detail": f"Body too large (max {MAX_BODY_BYTES // 1024 // 1024} MB)"},
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        return await call_next(request)

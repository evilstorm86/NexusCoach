# NexusCoach

Multi-tenant AI coaching platform. Digital Twin from wearable, body composition,
nutrition and training data. **Not a medical device — no diagnosis, no treatment.**

## Stack

FastAPI + PostgreSQL + Next.js (PWA) + OpenRouter, on Docker Compose behind a
Cloudflare Tunnel. Target host: Oracle Cloud VM, Ubuntu 24.04, 2 vCPU / 2 GB.

## Layout

```
api/    FastAPI backend
web/    Next.js frontend
```

## Run

```bash
cp .env.example .env    # fill in secrets
docker compose up --build
```

API on `:8000`, web on `:3000` (internal — exposed only via the tunnel).
Health check: `docker compose exec api curl -s localhost:8000/health`.

## Auth

| Endpoint | Notes |
|---|---|
| `POST /auth/register` | `{email, password}`, password ≥ 10 chars, role `user` |
| `POST /auth/login` | form-encoded `username`/`password` → `{access_token}` (12 h) |
| `GET /auth/me` | `Authorization: Bearer <token>` |

Passwords are bcrypt-hashed. Roles: `user`, `coach`, `admin` — `admin` passes every
guard. Protect a route with `Depends(require_role("coach"))`. Register/login/failed-login
are written to the `nexuscoach.audit` logger.

## Data model

| Table | Purpose |
|---|---|
| `users` | account + role |
| `metrics` | every normalized measurement: `user_id, ts, metric, value, unit, source` |
| `daily_snapshots` | per-user daily rollup, `(user_id, day)` → JSON |

`metrics` is deliberately one narrow table rather than one per domain — Withings, Apple
Health, Health Connect and CSV all emit the same shape (type + value + unit + time +
origin). `UNIQUE(user_id, source, metric, ts)` makes re-syncing a provider idempotent.

| Endpoint | Notes |
|---|---|
| `POST /metrics` | list of points; re-sending a point updates it |
| `GET /metrics` | `?metric=&since=&until=&limit=`, always scoped to the caller |

### Migrations

```bash
docker compose exec api alembic revision --autogenerate -m "what changed"
docker compose exec api alembic upgrade head    # also runs on container start
```

## Tests

```bash
docker compose run --rm api pytest
```

Tests run against a throwaway SQLite file, so no database container is needed.

## Roadmap

1. ✅ Repository & Docker
2. ✅ Authentication (JWT, roles user/coach/admin)
3. ✅ Database & domain model (alembic)
4. Withings OAuth2 sync
5. Imports (Apple Health, Health Connect, CSV)
6. Analytics
7. PWA
8. AI Coach
9. Scheduler (nightly 03:00)
10. Production hardening

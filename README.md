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

## Tests

```bash
docker compose run --rm api pytest
```

Tests run against a throwaway SQLite file, so no database container is needed.

## Roadmap

1. ✅ Repository & Docker
2. ✅ Authentication (JWT, roles user/coach/admin)
3. Database & domain model
4. Withings OAuth2 sync
5. Imports (Apple Health, Health Connect, CSV)
6. Analytics
7. PWA
8. AI Coach
9. Scheduler (nightly 03:00)
10. Production hardening

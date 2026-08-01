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

## PWA

Pages: Dashboard, Body, Nutrition, Training, Recovery, AI Coach, Integrations, Profile.
Installable (manifest + service worker), bottom nav on phones, light/dark from the OS.

Body / Nutrition / Training / Recovery are one component with different metric lists —
same job, so one page. Charts are inline SVG: daily readings as muted dots, the smoothed
trend as the colored line, with hover crosshair, legend and a table view. No chart
library.

### Look

Dark-only, orange accent, fully rounded cards and pill controls. Dark-only is deliberate:
the design commits to it, and a light theme nobody asked for is a second palette to keep
validated.

**The UI accent and the chart mark are different oranges on purpose.** `--accent`
(`#ff7a1a`) is the bright one for buttons, active nav and the FAB; `--series-1`
(`#e26410`) is a darker step for data. The bright orange sits above the dark-mode
lightness band and fails as a data color even though it reads well as UI — the chart
value was checked with the data-viz validator on this surface (CVD ΔE 12.8,
normal-vision 17.4, contrast ≥ 3:1). Buttons use near-black ink on accent; white on
orange doesn't clear 4.5:1.

On phones the bottom bar shows eight icons with the label on the active item only — eight
labelled items don't fit at 390 px.

`NEXT_PUBLIC_API_URL` is **baked in at build time** — it is a Docker build arg, not a
runtime env var, and it must be the URL the *browser* uses. `CORS_ORIGINS` on the API must
list the web origin.

## Settings (per-user API keys)

Users bring their own keys on **Profile → Settings** instead of everything living in
`.env`. Resolution is always **user setting → server default**, so a single-tenant
install still works with nothing configured in the UI.

| Endpoint | Notes |
|---|---|
| `GET /settings` | never returns a secret — `configured`, `source`, and a `…1234` hint |
| `PUT /settings/{name}` | store a value for the caller |
| `DELETE /settings/{name}` | drop it and fall back to the server value |

Settable: `openrouter_api_key`, `openrouter_model`, `withings_client_id`,
`withings_client_secret`. Anything else is a 404 — the list is a whitelist, not free-form
key/value storage.

Secrets are encrypted at rest with Fernet (`api/app/crypto.py`). `SECRETS_KEY` holds the
key; left blank it is derived from `JWT_SECRET`, which is fine for dev but means rotating
`JWT_SECRET` in production would orphan every stored secret — set it explicitly.

**Withings is the exception worth knowing:** `client_id` / `client_secret` are issued per
registered *application*, not per person, so most installs leave them blank and use the
deployment's own app. The per-user override exists for people who register their own at
developer.withings.com. `WITHINGS_REDIRECT_URI` stays server-side either way — it has to
point at this deployment.

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

## Analytics

| Endpoint | Returns |
|---|---|
| `GET /analytics/summary` | headline metrics: latest value, smoothed value, trend |
| `GET /analytics/series?metric=&days=` | raw daily points + EMA + trend |
| `GET /analytics/predict?metric=&goal=&days_ahead=` | projection, with its assumption stated |
| `POST /analytics/snapshot` | recompute one day's rollup (idempotent) |
| `GET /analytics/snapshots?days=` | recent daily snapshots |

Responses are split into `facts` (measured), `analysis` (smoothed / rate of change) and
`prediction` (extrapolated) — the separation the AI coach must preserve, enforced by the
data shape rather than by prompt wording.

Multiple readings in a day collapse to one: summed for counters (steps, kcal, macros),
averaged for levels (weight, heart rate). Trends are a least-squares fit over the last 28
days and return `null` rather than a slope drawn through two points.

**No pandas / scikit-learn / XGBoost.** One person's data is a few hundred points per
metric per year; `statistics.linear_regression` and a time-weighted EMA cover it, and the
ML stack would cost ~500 MB of image on a 2 GB VM. The ceiling is documented in
`api/app/analytics.py` — seasonality or multi-metric models are where numpy earns its keep.

## AI Coach

| Endpoint | Notes |
|---|---|
| `POST /coach/ask` | `{question, history?}` — history is resent by the client, not stored |
| `POST /coach/insight` | today's briefing, cached on the daily snapshot; `?refresh=true` to force |

OpenRouter only (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, default `anthropic/claude-opus-5`).
Returns 503 when unconfigured.

The coach never touches the database. It gets a JSON context built from the same
analytics the UI shows — already split into `facts` / `analysis` / `prediction` — and is
instructed to keep those apart and to never state a number that isn't in it. It is told
plainly that it is not a clinician: no diagnosis, no treatment, no dosages. With no data
at all, `/coach/insight` returns 409 rather than asking the model to invent something.

Client-supplied history is filtered to `user` and `assistant` turns, so a caller cannot
inject a `system` message into the prompt.

## Imports

| Endpoint | Accepts |
|---|---|
| `POST /imports/csv` | `ts,metric,value,unit` (+ optional `source`), UTF-8 |
| `POST /imports/apple-health` | `export.xml` or the `export.zip` the Health app produces |

Apple body-composition records are kept at full resolution; high-frequency ones (steps,
heart rate, energy, macros) are rolled up to one value per day during the parse — a year
of raw samples would be hundreds of thousands of rows and the analytics only read the
daily figure. Percentages are normalized (Apple's `0.221` → `22.1`). Sleep stages are
categories, not scalars, and are skipped.

**Health Connect** has no export file: the Android client reads the SDK and POSTs the same
point shape to `/metrics`. No separate endpoint.

## Withings

Create an app at [developer.withings.com](https://developer.withings.com/dashboard/), set
its callback to `WITHINGS_REDIRECT_URI`, and fill the three `WITHINGS_*` vars in `.env`.

| Endpoint | Notes |
|---|---|
| `GET /integrations/withings/connect` | returns the URL to send the user to |
| `GET /integrations/withings/callback` | Withings redirects here; exchanges code for tokens |
| `POST /integrations/withings/sync` | pulls measures since the last sync |
| `DELETE /integrations/withings` | drops the connection |

`state` is a 10-minute JWT, so there is no server-side state store. Access tokens are
refreshed automatically when within a minute of expiry. Body-composition measures land in
`metrics` with `source="withings"`; re-syncing never duplicates them.

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
4. ✅ Withings OAuth2 sync *(untested against the live API — needs credentials)*
5. ✅ Imports (Apple Health, Health Connect, CSV)
6. ✅ Analytics
7. ✅ PWA
8. ✅ AI Coach
9. Scheduler (nightly 03:00)
10. Production hardening

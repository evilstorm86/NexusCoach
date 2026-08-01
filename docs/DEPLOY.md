# Deploying NexusCoach

Target: one Oracle Cloud VM, Ubuntu 24.04, 2 vCPU / 2 GB, everything in Docker Compose
behind a Cloudflare Tunnel. No Nginx.

> **This has not been run end to end yet.** Every test and screenshot in this repo comes
> from SQLite and a local uvicorn. The Postgres path, the container builds and the tunnel
> are written but unexercised — treat the first deploy as a test, and expect to fix
> something. Where a step is most likely to be the one that breaks, it says so.

---

## 1. Prerequisites

On the VM:

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER" && newgrp docker
docker --version && docker compose version
```

In Cloudflare Zero Trust: create a tunnel, add a public hostname pointing at
`http://web:3000`, and copy the tunnel token. Add a second hostname for the API pointing
at `http://api:8000` — the browser calls the API directly, so it needs its own public
name.

---

## 2. Clone and configure

```bash
git clone https://github.com/evilstorm86/NexusCoach.git && cd NexusCoach
cp .env.example .env
```

Generate the two secrets — do not reuse them from anywhere else:

```bash
# JWT_SECRET
openssl rand -hex 32
# SECRETS_KEY (Fernet: base64, exactly 32 bytes)
docker run --rm python:3.12-slim sh -c "pip -q install cryptography && python -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

Fill in `.env`:

| Variable | Notes |
|---|---|
| `POSTGRES_PASSWORD` | any long random string |
| `DATABASE_URL` | must contain the same password |
| `JWT_SECRET` | from above |
| `SECRETS_KEY` | from above. **Set it.** Left blank it derives from `JWT_SECRET`, and then rotating `JWT_SECRET` orphans every stored API key and OAuth token |
| `CORS_ORIGINS` | the web hostname, e.g. `https://app.example.com` |
| `NEXT_PUBLIC_API_URL` | the **API** hostname, e.g. `https://api.example.com` |
| `CLOUDFLARE_TUNNEL_TOKEN` | from the tunnel |
| `WITHINGS_*` | optional — see §7 |
| `OPENROUTER_*` | optional — users can bring their own key instead |

> `NEXT_PUBLIC_API_URL` is **baked into the JavaScript bundle at build time**. Changing it
> later requires `docker compose build web`, not a restart. Getting this wrong is the most
> likely first-deploy failure: the app loads, then every request fails in the browser.

---

## 3. Build and start

```bash
docker compose up -d --build
docker compose ps
```

The first build is the slow part — Next.js compiles on a 2 vCPU box. If `web` is OOM-killed
during `npm run build`, add swap and retry:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Migrations run automatically when the `api` container starts (`alembic upgrade head`).

---

## 4. Verify

```bash
# API health — the image has no curl, so use python
docker compose exec api python -c \
  "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').read())"
# expect: {"status":"ok","database":"up","scheduler":true}

docker compose logs api | grep -i "nightly scheduler"
# expect: nightly scheduler on, 03:00 UTC
```

Then load the web hostname in a browser and register an account. If the page renders but
every request fails, `NEXT_PUBLIC_API_URL` or `CORS_ORIGINS` is wrong — see §3.

---

## 5. Create the first admin

Registration always creates a plain `user`. Admin endpoints (`/admin/jobs`) are unreachable
until someone is promoted:

```bash
docker compose exec api python -m app.promote --list
docker compose exec api python -m app.promote you@example.com admin
```

Verify:

```bash
TOKEN=$(curl -s -X POST https://api.example.com/auth/login \
  -d "username=you@example.com&password=..." | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" https://api.example.com/admin/jobs
```

Demote with `... python -m app.promote you@example.com user`.

---

## 6. Backups

**Nothing backs up automatically.** The `pgdata` volume is the only copy of everyone's
health history. Set this up on day one, not after the first scare.

```bash
# Nightly dump at 02:30, before the 03:00 sync, keeping 14 days.
mkdir -p ~/backups
cat > ~/backup-nexuscoach.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/NexusCoach"
out=~/backups/nexuscoach-$(date +%F).sql.gz
docker compose exec -T db pg_dump -U nexus nexuscoach | gzip > "$out"
find ~/backups -name 'nexuscoach-*.sql.gz' -mtime +14 -delete
EOF
chmod +x ~/backup-nexuscoach.sh
(crontab -l 2>/dev/null; echo "30 2 * * * $HOME/backup-nexuscoach.sh") | crontab -
```

Restore:

```bash
docker compose stop api web
gunzip -c ~/backups/nexuscoach-2026-08-01.sql.gz | \
  docker compose exec -T db psql -U nexus -d nexuscoach
docker compose start api web
```

> A dump is worthless until you have restored one. Do a restore into a scratch database
> once, now, while nothing depends on it. **Copy the dumps off the VM** — a backup on the
> same disk as the database is not a backup.
>
> `SECRETS_KEY` is **not** in the dump. Store it with your backups, separately: without it
> every encrypted API key and OAuth token in a restored database is unreadable.

---

## 7. Withings (optional)

Register an app at [developer.withings.com](https://developer.withings.com/dashboard/) and
set its callback to `https://api.example.com/integrations/withings/callback`. Put the
credentials in `.env` as the deployment-wide default, or leave them blank and let each user
add their own under **Profile → Settings**.

The Withings integration has never run against the live API. First connect + sync is the
real test; failures surface as a 502 with the raw payload in the logs:

```bash
docker compose logs -f api | grep withings
```

---

## 8. Upgrades

```bash
cd ~/NexusCoach && ~/backup-nexuscoach.sh   # always dump first
git pull
docker compose up -d --build                # migrations run on api start
docker compose logs --tail=50 api
```

Rollback:

```bash
git checkout <previous-sha> && docker compose up -d --build
```

Alembic has downgrades, but they have never been run — prefer restoring a dump over
`alembic downgrade` unless you have tested it.

---

## 9. Operations

```bash
docker compose logs -f api                       # follow
docker compose exec api python -m app.promote --list
docker stats --no-stream                         # against the 512M limits
```

Trigger the nightly sync by hand (admin token):

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://api.example.com/admin/jobs/nightly
curl -s -H "Authorization: Bearer $TOKEN" https://api.example.com/admin/jobs   # last 30 runs
```

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| Page loads, every request fails | `NEXT_PUBLIC_API_URL` wrong, or the API host missing from `CORS_ORIGINS`. Rebuild `web` after changing it |
| `api` restarts in a loop | Migration failed. `docker compose logs api` — usually `DATABASE_URL` or a Postgres password mismatch |
| `web` build killed | Out of memory. Add swap (§3) |
| Coach returns 503 | No OpenRouter key, server-wide or per user |
| Coach returns 502 | OpenRouter rejected the key or the model slug |
| Nightly never runs | `RUN_SCHEDULER=false`, or check `/health` for `"scheduler": true` |
| Stored secrets unreadable after a restore | `SECRETS_KEY` changed or was derived from a rotated `JWT_SECRET` |

### Scaling past one container

The rate limiter counts in-process and the scheduler is an in-process task. A second `api`
replica needs `RUN_SCHEDULER=false` on the extra one (the `job_runs` unique key already
prevents a double run) and a shared store for the limiter — see `api/app/security.py`.

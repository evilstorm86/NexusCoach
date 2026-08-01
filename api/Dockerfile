FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user: nothing here needs root, and the container mounts no volumes.
RUN useradd --system --uid 10001 nexus && chown -R nexus /app
USER nexus

# One worker on purpose. Two vCPU shared with Postgres and Next.js, and the nightly
# scheduler lives in-process — a second worker would run it twice (the job_runs unique
# key would catch that, but there is nothing to gain).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]

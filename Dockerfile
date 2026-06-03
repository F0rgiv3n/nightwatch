# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — builder: install dependencies into an isolated virtualenv.
# Keeping build here means the final image carries no pip cache or toolchain.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Create the venv we'll copy into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies first for better layer caching (changes rarely).
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim image, non-root user, no build tools.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as an unprivileged user; own the data dir for the SQLite volume.
RUN useradd --create-home --uid 10001 sentinel \
    && mkdir -p /app/data \
    && chown -R sentinel:sentinel /app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=sentinel:sentinel sentinel ./sentinel
COPY --chown=sentinel:sentinel config.example.yaml ./config.example.yaml

USER sentinel

# Persist history (SQLite + heartbeat) across container restarts.
VOLUME ["/app/data"]

# Healthy = the scheduler touched the heartbeat within the last 30 minutes.
HEALTHCHECK --interval=5m --timeout=10s --start-period=1m --retries=3 \
    CMD python -c "import os,sys,time; f='data/heartbeat'; \
sys.exit(0 if os.path.exists(f) and time.time()-os.path.getmtime(f) < 1800 else 1)"

# Mount your real config at /app/config.yaml (compose does this for you).
ENTRYPOINT ["python", "-m", "sentinel"]
CMD ["run", "-c", "config.yaml"]

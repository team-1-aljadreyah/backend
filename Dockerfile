
# =====================================================
# Al-Jadreyah Backend - Production Docker Image
# Python 3.12 / FastAPI / Uvicorn
# =====================================================

# ---------- Build Stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir=/wheels \
    -r requirements.txt


# ---------- Production Runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Create non-root application user
RUN groupadd --gid 1001 appuser && \
    useradd \
      --uid 1001 \
      --gid 1001 \
      --no-create-home \
      --shell /usr/sbin/nologin \
      appuser

# Install pre-built dependencies
COPY --from=builder /wheels /wheels
COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install \
    --no-cache-dir \
    --no-index \
    --find-links=/wheels \
    -r /tmp/requirements.txt && \
    rm -rf /wheels /tmp/requirements.txt

# Copy application
COPY --chown=1001:1001 app/ ./app/
COPY --chown=1001:1001 database/ ./database/

# Persistent upload directory mount point
RUN mkdir -p /app/uploads && \
    chown -R 1001:1001 /app

# Run as non-root
USER 1001:1001

EXPOSE 8000


# Database-aware health check

HEALTHCHECK \
    --interval=10s \
    --timeout=5s \
    --start-period=60s \
    --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"]


# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]

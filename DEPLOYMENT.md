# Production Deployment Guide — Al-Jadreyah Clinic Backend

This guide outlines the production deployment architecture, security hardening, container specifications, and monitoring configuration.

---

## 1. Production Architecture Overview

The backend is deployed as a hardened, stateless container orchestrated via Docker Compose or Kubernetes, connecting directly to Supabase PostgreSQL:

```
[Internet] --> [Reverse Proxy / Cloudflare TLS Termination]
                      |
                      v
             [Uvicorn ASGI Workers (4-8)]
                      |
                      v
      [Supabase Managed PostgreSQL 16+ Pooler]
```

### Production Security Hardening
- **Stateless Execution:** Zero shared local filesystem state; all persistent data resides in PostgreSQL or authenticated Supabase object storage.
- **Zero Redis Dependency:** Fully decoupled from Redis; no external caching services required.
- **Read-Only Root Filesystem:** Container runs with `read_only: true`, mounting `/tmp` as a restricted `tmpfs (size=64m)`.
- **Dropped Linux Capabilities:** `cap_drop: [ALL]`, `no-new-privileges: true`.
- **Dedicated Non-Root User:** Process executes under unprivileged UID `10001` (`appuser`).

---

## 2. Environment Variables Specification

The production environment file (`/etc/aljadreyah/backend.env` or `.env`) must configure the following:

```ini
# Application Core
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
APP_TIMEZONE=Asia/Baghdad
SECRET_KEY=<32-char-cryptographically-random-secret>

# Database Connection (Supabase Transaction Pooler)
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<supabase-host>:5432/postgres?ssl=require
DB_POOL_SIZE=15
DB_MAX_OVERFLOW=15

# Real-Time PostgreSQL Outbox (Zero Redis)
REALTIME_POLL_INTERVAL_SECONDS=0.5
REALTIME_BATCH_SIZE=50
REALTIME_TICKET_EXPIRE_SECONDS=60

# Qi Card Sandbox Payment Gateway
QI_ENV=sandbox
QI_BASE_URL=https://uat-sandbox-3ds-api.qi.iq/api/v1
QI_USERNAME=paymentgatewaytest
QI_PASSWORD=WHaNFE5C3qlChqNbAzH4
QI_TERMINAL_ID=237984
QI_WEBHOOK_PUBLIC_KEY_PEM=

# Storage & CORS
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_STORAGE_BUCKET=lab-results
FRONTEND_ORIGINS=https://alrahma.ama8.uk,http://localhost:3000
LOG_LEVEL=INFO
```

---

## 3. Container Deployment Procedures

### Build Production Image
```bash
docker build -t aljadreyah-backend:latest -f Dockerfile .
```

### Run Production Container with Docker Compose
```bash
docker compose -f compose.production.yaml up -d
```

### Healthcheck Verification
FastAPI provides dedicated probes for load balancers and orchestrators:
```bash
# Liveness Probe
curl -f http://127.0.0.1:8000/health/live

# Readiness Probe (Verifies PostgreSQL connection)
curl -f http://127.0.0.1:8000/health/ready
```

---

## 4. Multi-Worker Process Model

In production, run Uvicorn with multiple asynchronous workers:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --loop uvloop
```
Because connection tickets and outbox events are persisted in PostgreSQL, clients can connect to any worker process without sticky sessions.

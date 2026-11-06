# Al-Jadreyah Clinic Management System — Deployment Guide

This guide describes how to configure, initialize, and deploy the Al-Jadreyah Clinic Management System backend in a production environment using **Supabase PostgreSQL** and **FastAPI**.

---

## 1. Architecture Overview

```
 [ Next.js Frontend ] 
         │ (HTTPS / REST API)
         ▼
 [ Reverse Proxy (Nginx / Caddy / Cloud Run) ]
         │ (HTTP / Unix Socket)
         ▼
 [ FastAPI Application (Uvicorn / Gunicorn) ]
         │
 ┌───────┴────────────────────────┐
 │ (AsyncPG / TCP 5432 or 6543)    │ (HTTPS REST API / S3)
 ▼                                ▼
[ Supabase PostgreSQL ]     [ Supabase Storage ]
- RLS Policies              - Private Bucket: lab-results
- Triggers & Functions      - Storage RLS Policies
- Single schema.sql truth
```

---

## 2. Supabase Database Initialization (STRICT SINGLE SQL FILE)

The entire relational schema, table structures, RLS policies, triggers, and safe initial seed data are defined in **exactly one file**:
```
backend/database/schema.sql
```

### Steps to Initialize in Supabase:
1. Log in to your **Supabase Dashboard** (https://app.supabase.com).
2. Select your project (or create a new project named `aljadreyah-clinic`).
3. In the left navigation pane, click on the **SQL Editor** (icon `>_`).
4. Click **New Query**.
5. Copy the entire contents of `backend/database/schema.sql`.
6. Paste the SQL into the editor window.
7. Click **Run** (or press `Ctrl+Enter` / `Cmd+Enter`).
8. Verify the output displays `Success. No rows returned` (or table creation logs).

> [!NOTE]
> The SQL script is completely idempotent: all `CREATE TABLE`, `CREATE INDEX`, `CREATE TYPE`, and `INSERT` statements utilize `IF NOT EXISTS` or `ON CONFLICT DO NOTHING`. Running it repeatedly will not wipe or duplicate data.

### Storage Verification:
The SQL script automatically creates the private storage bucket:
- **Bucket ID:** `lab-results`
- **Public:** `false` (Private — access strictly governed by authenticated RLS policies)

---

## 3. Configuration & Environment Variables

Copy `.env.example` to `.env` in the `backend/` directory:
```bash
cp backend/.env.example backend/.env
```

Set the following variables:

| Variable | Description | Example / Default |
|---|---|---|
| `APP_ENV` | Application environment | `production` |
| `APP_DEBUG` | Enable debug logs and detailed traceback | `false` |
| `APP_PORT` | Port for the FastAPI server | `8000` |
| `APP_TIMEZONE` | Clinic local timezone | `Asia/Baghdad` |
| `SECRET_KEY` | 32+ character cryptographically random string for JWT signatures | Generate via `openssl rand -hex 32` |
| `DATABASE_URL` | AsyncPG PostgreSQL connection URL | `postgresql+asyncpg://postgres:[PASS]@[HOST]:5432/postgres` |
| `SUPABASE_URL` | Supabase project URL | `https://[PROJECT_REF].supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase Anon Public Key | `eyJhbGci...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role Key (secure backend calls) | `eyJhbGci...` |
| `SUPABASE_STORAGE_BUCKET` | Supabase Storage bucket for medical lab files | `lab-results` |
| `FRONTEND_ORIGINS` | Comma-separated CORS allowed origins | `https://clinic.aljadreyah.iq,http://localhost:3000` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

### Connection String Notes for Supabase:
- **Direct Connection (Default, Port 5432):**
  `postgresql+asyncpg://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres`
- **Session Pooling (Port 5432):** Recommended for long-lived async connections.
- **Transaction Pooling (Port 6543):** If used, disable prepared statements in AsyncPG.

---

## 4. Docker Deployment

### 4.1 Production Dockerfile
Build the self-contained Docker image:
```bash
docker build -t aljadreyah-backend:latest -f backend/Dockerfile backend/
```

### 4.2 Running the Container
```bash
docker run -d \
  --name aljadreyah-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file backend/.env \
  aljadreyah-backend:latest
```

### 4.3 Full-Stack Docker Compose (Optional Local Hosting)
If hosting locally without external Supabase, use `docker-compose.yml`:
```bash
docker compose up -d
```
This boots:
- PostgreSQL 16 (initialized with `backend/database/schema.sql`)
- FastAPI Backend on `http://localhost:8000`

---

## 5. Linux Server / VPS Deployment (Systemd + Nginx)

### 5.1 Systemd Service Unit
Create `/etc/systemd/system/aljadreyah-api.service`:
```ini
[Unit]
Description=Al-Jadreyah Clinic Management System API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/aljadreyah/backend
EnvironmentFile=/var/www/aljadreyah/backend/.env
ExecStart=/var/www/aljadreyah/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aljadreyah-api
sudo systemctl start aljadreyah-api
```

### 5.2 Nginx Reverse Proxy Configuration
Create `/etc/nginx/sites-available/aljadreyah.conf`:
```nginx
server {
    listen 80;
    server_name api.aljadreyah-clinic.iq;

    # Redirect all HTTP traffic to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.aljadreyah-clinic.iq;

    ssl_certificate /etc/letsencrypt/live/api.aljadreyah-clinic.iq/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.aljadreyah-clinic.iq/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }
}
```

---

## 6. Health Checks & Verification

### 6.1 Automated Liveness Probe
```bash
curl -f http://localhost:8000/health
```
Response:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "version": "1.0.0",
    "environment": "production"
  }
}
```

### 6.2 Running Automated Verification Test Suite
```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```
Ensure all 21 automated tests pass (`Ran 21 tests ... OK`).

---

## 7. Connecting Next.js Frontend

To connect the Next.js frontend in `Front/`:
1. In `Front/.env.local` (or `Front/.env`):
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_USE_MOCK=false
   ```
2. Re-build or restart the frontend development server:
   ```bash
   cd Front
   npm run build
   npm start
   ```
3. Open `http://localhost:3000` in your browser. The frontend will now communicate directly with the live FastAPI backend!

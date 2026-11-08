# Database Migrations Guide — Alembic & PostgreSQL

This document outlines the migration lifecycle, version tracking, and execution protocols for the Al-Jadreyah Clinic database.

---

## 1. Migration Framework Overview

Database schema changes are tracked and executed using **Alembic** configured with SQLAlchemy 2.0 async engine compatibility.

### Directory Structure
```
backend/
├── alembic.ini                   # Alembic global configuration
├── alembic/
│   ├── env.py                   # Async migration environment runner
│   ├── script.py.mako           # Migration template
│   └── versions/
│       ├── 0001_initial_schema.py             # Baseline schema
│       └── 0002_realtime_outbox_and_qi_payments.py # Outbox, tickets, rate limit tables & triggers
└── database/
    └── schema.sql               # Single Source of Truth reference DDL
```

---

## 2. Active Migrations

| Revision ID | Description | Down Revision |
| ----------- | ----------- | ------------- |
| `0001_initial_schema` | Baseline clinic schema (clinical, financial, pharmacy, governance) | `None` |
| `0002_realtime_outbox_qi` | Real-time connection tickets, transactional outbox, rate limiting, and PostgreSQL triggers | `0001_initial_schema` |

---

## 3. Migration Commands

### Running Migrations Up to Latest Head
```bash
alembic upgrade head
```

### Checking Current Migration Version
```bash
alembic current
```

### Viewing History of Applied Migrations
```bash
alembic history --verbose
```

### Rolling Back the Most Recent Migration
```bash
alembic downgrade -1
```

### Generating a New Migration
```bash
alembic revision -m "add_new_feature_table"
```

---

## 4. Production Migration Safety Protocol

1. **Safety Rule:** NEVER execute manual ad-hoc DDL queries or destructive commands against the production Supabase database.
2. **Review DDL Before Applying:** Always inspect the generated migration script for proper column types, index definitions, and backward compatibility.
3. **Run Against Test Database First:** Verify migrations against a local disposable PostgreSQL database or test harness before triggering deployment.
4. **Zero Downtime Deployment:** All new columns should be added as nullable or with safe server defaults to prevent blocking ongoing application operations.

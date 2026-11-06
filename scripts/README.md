# Operational & Maintenance Scripts

This directory contains standalone utility, migration, and stress-testing scripts for developer and administrative use.

## Available Scripts

- **`migrate_tasks.py`**: Applies PostgreSQL DDL updates and GiST exclusion constraints to live PostgreSQL/Supabase instances.
- **`test_all_endpoints.py`**: Smoke tests all backend API endpoints against running development or production servers.
- **`stress_test_report.json`**: Historical benchmark and stress test execution metrics.
- **`inspect_book_bundle.py`**: Diagnostic utility for appointment booking payloads and slot calculations.

## Running Scripts

Ensure your virtual environment is active and `PYTHONPATH` includes the backend root:

```bash
# On Linux / macOS:
export PYTHONPATH=.
python scripts/test_all_endpoints.py

# On Windows PowerShell:
$env:PYTHONPATH="."
python scripts/test_all_endpoints.py
```

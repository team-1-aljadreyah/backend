# Contributing to Al-Jadreyah Clinic Backend

Thank you for your interest in contributing to the Al-Jadreyah Clinic Management System Backend. This guide outlines the workflow, development standards, and code quality expectations required for all contributions.

---

## 1. Development Workflow

### A. Fork & Clone
1. Fork the repository to your GitHub account.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/al-jadreyah-backend.git
   cd al-jadreyah-backend
   ```

### B. Environment Setup
1. Create and activate a Python 3.12 virtual environment:
   ```bash
   python -m venv .venv

   # Linux / macOS:
   source .venv/bin/activate

   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   ```
2. Install development dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Configure your local environment file:
   ```bash
   cp .env.example .env
   ```

---

## 2. Branching Strategy

Follow standard Git branching conventions:
- `feature/<short-description>`: New functional capabilities or endpoints.
- `bugfix/<issue-number>-<short-description>`: Bug and regression fixes.
- `hotfix/<critical-issue>`: Production priority fixes.
- `refactor/<module-name>`: Code restructuring without functional changes.
- `docs/<topic>`: Documentation updates and architectural revisions.

Always branch from `main` and ensure your branch is up to date before submitting a Pull Request:
```bash
git checkout main
git pull origin main
git checkout -b feature/patient-tagging
```

---

## 3. Commit Message Standards

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

### Types
- `feat`: A new feature or endpoint.
- `fix`: A bug fix.
- `docs`: Documentation changes only.
- `style`: Formatting, missing semicolons, etc. (no production code change).
- `refactor`: Refactoring production code without changing behavior.
- `perf`: Code change that improves performance.
- `test`: Adding missing tests or correcting existing tests.
- `chore`: Build tasks, package manager configs, etc.

*Examples*:
- `feat(patients): add fuzzy search and duplicate scoring endpoint`
- `fix(appointments): enforce GiST exclusion constraint on active bookings`
- `test(concurrency): add 20 parallel slot booking tests`

---

## 4. Coding Standards & Conventions

1. **Architecture & Separation of Concerns**:
   - `app/api/routes/`: Route definitions, request validation, envelope responses. Keep business logic out of router handlers.
   - `app/services/`: Transaction orchestration, business rules, and multi-table updates.
   - `app/schemas/`: Pydantic models for request bodies and response serialization.
   - `app/database/models/`: SQLAlchemy declarative models.
   - `database/schema.sql`: Single unified SQL source of truth.
2. **Response Envelope**:
   - All successful responses must return `success_response(data)` producing `{ "success": true, "data": ... }`.
   - Exceptions must inherit from `AppException` in `app.core.exceptions` to produce `{ "success": false, "code": "...", "message": "..." }`.
3. **Database Integrity**:
   - Never hard-delete financial transactions (`payments`, `expenses`).
   - Never hard-delete patient medical files; use soft-merging (`merged_into_patient_id`).
   - Use row locking (`with_for_update()`) for race-sensitive operations.

---

## 5. Testing Requirements

Every Pull Request must include automated tests verifying:
- Happy path execution.
- Edge cases and validation rejections (422, 404).
- Role-based access control (RBAC) permissions (403).
- Concurrency and idempotency behavior where applicable.

Run the test suite before opening a PR:
```bash
pytest -v
```

All 35+ existing tests must pass with zero failures.

---

## 6. Pull Request Submission Checklist

Before submitting your PR, verify:

- [ ] Code follows project formatting and styling standards.
- [ ] No hardcoded passwords, tokens, API keys, or live credentials exist.
- [ ] All new endpoints are documented in OpenAPI / Pydantic schemas.
- [ ] Automated tests have been added and `pytest -v` passes completely.
- [ ] PR title follows Conventional Commits format.
- [ ] Branch is rebased against the latest `main`.

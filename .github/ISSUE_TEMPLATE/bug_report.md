---
name: Bug Report
about: Create a report to help us improve the clinic management backend
title: "[BUG]: "
labels: ["bug"]
assignees: ""
---

## Description
A clear and concise description of the bug.

## Endpoint & Method
- **Endpoint**: `POST /appointments` / `GET /patients/{id}/file` etc.
- **HTTP Method**: GET / POST / PUT / PATCH / DELETE
- **Authenticated Role**: `doctor` / `reception` / `manager` / `patient` / `pharmacy` / `lab` / `accountant`

## Steps to Reproduce
1. Call endpoint `...` with payload `{ ... }`
2. Pass header `...`
3. Observe error response

## Expected Behavior
What you expected to happen according to the API contract.

## Actual Behavior
Include response status code and JSON error body:
```json
{
  "success": false,
  "code": "...",
  "message": "..."
}
```

## Environment
- OS: [e.g. Ubuntu 22.04, Windows 11]
- Python Version: [e.g. 3.12.0]
- Database: [Supabase PostgreSQL / Local PostgreSQL / SQLite]

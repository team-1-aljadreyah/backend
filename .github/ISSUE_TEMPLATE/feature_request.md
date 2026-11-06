---
name: Feature Request
about: Suggest an idea or new endpoint for the clinic management backend
title: "[FEATURE]: "
labels: ["enhancement"]
assignees: ""
---

## Summary
A concise explanation of the proposed feature or endpoint.

## Problem Statement
What clinical, administrative, or operational problem does this solve?

## Proposed Solution & Endpoint Design
- **Path**: e.g. `POST /patients/{id}/tags`
- **Authorized Roles**: e.g. `doctor`, `manager`
- **Request Schema**:
```json
{
  "tag": "diabetic"
}
```
- **Response Schema**:
```json
{
  "success": true,
  "data": { ... }
}
```

## Database Schema Impact
Does this require schema changes in `database/schema.sql` or new relational tables?

## Alternatives Considered
Any alternative approaches or workarounds considered.

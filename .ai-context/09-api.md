# 09-api.md

# API Contracts

## Purpose

This document defines the communication contract between the frontend and backend.

All API endpoints should follow consistent request, response, and error patterns. As new endpoints are introduced, they should be documented here to maintain clear boundaries between frontend expectations and backend implementation.

---

# API Principles

* The frontend communicates exclusively through documented API endpoints.
* The frontend should not access the database directly.
* API responses should follow a consistent structure.
* Business logic remains within backend services.
* Backend implementation details should remain hidden behind API contracts.
* Refund endpoints should expose backend-evaluated eligibility and lifecycle outcomes.
* Clients must not submit or override authoritative refund eligibility state.

---

# Standard Response

Successful responses should follow the standard response shape.

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

---

# Standard Error

Failed requests should return a standardized error response.

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "REFUND_NOT_ELIGIBLE",
    "message": "This item is outside the refund window."
  },
  "meta": {}
}
```

---

# Endpoint Documentation

Each endpoint should document:

* Route
* HTTP Method
* Purpose
* Authentication Requirements
* Request Body
* Response Body
* Possible Error Codes
* Notes

Example:

```text
POST /api/chat

Purpose
Submit a customer or administrator message to the AI orchestration layer.

Request
{
  "sessionId": "...",
  "message": "..."
}

Response
Standard Response

Errors
INVALID_SESSION
MODEL_ERROR
TOOL_EXECUTION_FAILED
```

---

# Implemented Endpoints

## GET /health

Purpose
Verify that the FastAPI backend process is running and able to return the standard API response envelope.

Authentication Requirements
None.

Request Body
None.

Response Body

```json
{
  "success": true,
  "data": {
    "service": "refunds-ai-api",
    "status": "ok"
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
None for normal readiness checks.

Notes
This endpoint is part of the development foundation scaffold only. It does not validate database, AI service, or business workflow readiness.

## GET /health/database

Purpose
Verify that the backend can complete a Supabase PostgreSQL handshake using the configured database connection string.

Authentication Requirements
None.

Request Body
None.

Success Response Body

```json
{
  "success": true,
  "data": {
    "provider": "supabase-postgres",
    "configured": true,
    "connected": true
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Configuration Error Response Body

```json
{
  "success": false,
  "data": {
    "provider": "supabase-postgres",
    "configured": false,
    "connected": false
  },
  "error": {
    "code": "DATABASE_NOT_CONFIGURED",
    "message": "SUPABASE_DB_URL is not configured."
  },
  "meta": {
    "timestamp": "..."
  }
}
```

Connection Error Response Body

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "DATABASE_CONNECTION_FAILED",
    "message": "Database handshake failed."
  },
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
DATABASE_NOT_CONFIGURED
DATABASE_CONNECTION_FAILED

Notes
This endpoint validates database connectivity only. It returns an HTTP status code `503 Service Unavailable` when database configuration is missing or connectivity checks fail. It does not validate schema, migrations, seed data, or business readiness.

---

# Planned Refund API Contract

Refund API endpoints should follow the embedded-detail-table architecture.

Read endpoints should load `purchases` and the matching purchase detail record, then return backend-evaluated refund eligibility and supporting facts.

Mutating endpoints should:

1. Accept a refund request command.
2. Load the purchase.
3. Load the matching purchase detail record.
4. Verify the refund window.
5. Evaluate product-specific policy.
6. Execute the approved strategy.
7. Persist lifecycle updates to the owning detail table.

Clients should never send fields such as `eligible`, `refunded`, `refund_pending`, or model-generated policy conclusions as authoritative input. Those values are computed inside backend services.

Clients should also never send database-derived refund deadline values. Deadline fields are computed by PostgreSQL triggers from persisted purchase and detail-table state.

No API contract should require or expose a standalone `refunds` table.

---

# Versioning

As the backend evolves, this document should remain synchronized with the implemented API surface.

Adding, modifying, or removing endpoints should include corresponding updates to this document to preserve a clear contract between the frontend and backend.

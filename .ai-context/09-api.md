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

# Versioning

As the backend evolves, this document should remain synchronized with the implemented API surface.

Adding, modifying, or removing endpoints should include corresponding updates to this document to preserve a clear contract between the frontend and backend.

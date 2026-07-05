# 09-api.md

# API Contracts

## Purpose

This document defines the communication contract between the frontend and backend.

All API endpoints should follow consistent request, response, and error patterns. As new endpoints are introduced, they should be documented here to maintain clear boundaries between frontend expectations and backend implementation.

---

# Versioning

As the backend evolves, this document should remain synchronized with the implemented API surface.

Adding, modifying, or removing endpoints should include corresponding updates to this document to preserve a clear contract between the frontend and backend.

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

## POST /api/chat

Purpose
Accept a text chat message from the frontend help panel and return the phase-one static AI infrastructure response.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body

```json
{
  "message": "How many digital purchases have I made?",
  "customer_id": "10000000-0000-4000-8000-000000000001",
  "purchase_id": "40000000-0000-4000-8000-000000000001"
}
```

`message` is required to contain non-empty text after trimming whitespace. `customer_id` and `purchase_id` are optional context hints for future orchestration and are not authoritative authentication or authorization inputs.

Success Response Body

```json
{
  "success": true,
  "data": {
    "message": {
      "role": "assistant",
      "content": "I can help answer questions about your purchases. The AI workflow infrastructure is connected, and LangGraph orchestration will be enabled in a later phase."
    },
    "model": "gpt-5.4-mini",
    "graph_ready": false
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Invalid Message Response Body

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_CHAT_MESSAGE",
    "message": "Chat message must not be empty."
  },
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
INVALID_CHAT_MESSAGE

Notes
This endpoint is an AI Agent Integration phase-one seam only. It validates message text, returns a static assistant response, and emits structured application log events for message receipt and response generation. It does not call OpenAI, execute LangGraph, call backend tools, inspect purchase data, evaluate refund policy, capture voice input, or mutate business state.

## GET /api/users/mock

Purpose
Return selectable mock users for the frontend user-selection flow.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body

```json
{
  "success": true,
  "data": {
    "users": [
      {
        "id": "10000000-0000-4000-8000-000000000001",
        "first_name": "John",
        "last_name": "Smith",
        "created_at": "2026-07-03T00:00:00Z",
        "display_name": "John Smith",
        "roles": [
          {
            "key": "customer",
            "name": "Customer"
          }
        ]
      }
    ]
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
DATABASE_NOT_CONFIGURED

Notes
This endpoint reads `users`, `user_roles`, and `roles`. It does not implement production authentication.

## GET /api/users/{user_id}

Purpose
Return one selected mock user with role information.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body

```json
{
  "success": true,
  "data": {
    "user": {
      "id": "10000000-0000-4000-8000-000000000001",
      "first_name": "John",
      "last_name": "Smith",
      "created_at": "2026-07-03T00:00:00Z",
      "display_name": "John Smith",
      "roles": [
        {
          "key": "customer",
          "name": "Customer"
        }
      ]
    }
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
USER_NOT_FOUND
DATABASE_NOT_CONFIGURED

Notes
Role information is loaded through `user_roles` and `roles`; role data is not duplicated onto `users`.
`created_at` comes from `users.created_at` and may be used by the frontend for non-authoritative profile metadata such as "Customer Since".

## GET /api/users/{user_id}/purchases

Purpose
Return purchase history for one selected user with enough metadata for the frontend to render purchase cards and load the matching detail endpoint.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body

```json
{
  "success": true,
  "data": {
    "purchases": [
      {
        "id": "40000000-0000-4000-8000-000000000001",
        "order_number": "RAI-10001",
        "purchase_type": "physical",
        "product_name": "Wireless Headphones",
        "sku": "PHY-HEADPHONES-001",
        "amount_cents": 12999,
        "purchased_at": "2026-06-20T14:30:00Z",
        "status": "completed",
        "details_url": "/api/purchases/40000000-0000-4000-8000-000000000001/details"
      }
    ]
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
USER_NOT_FOUND
DATABASE_NOT_CONFIGURED

Notes
This endpoint reads `purchases` joined to `products`. The purchase row exposes `purchase_type` so the frontend can choose a detail presentation, but the frontend must not use `purchase_type` to choose a database-specific endpoint.

## GET /api/purchases/{purchase_id}/details

Purpose
Return the type-specific detail record for a purchase. The backend resolves the correct detail table from `purchases.purchase_type`.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body

```json
{
  "success": true,
  "data": {
    "purchase_id": "40000000-0000-4000-8000-000000000001",
    "purchase_type": "physical",
    "details": {
      "scheduled_delivery_at": "2026-06-22T14:30:00Z",
      "delivered_at": null,
      "return_status": "not_requested",
      "carrier": "UPS",
      "tracking_number": "TRK-RAI-10001",
      "accepted_by_carrier_at": null,
      "return_requested_at": null,
      "return_authorized_at": null,
      "return_received_at": null,
      "return_rejected_at": null,
      "return_rejection_reason": null,
      "refund_window_expires_at": "2026-07-20T14:30:00Z"
    }
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
PURCHASE_NOT_FOUND
PURCHASE_DETAILS_NOT_FOUND
DATABASE_NOT_CONFIGURED

Notes
Clients call one stable detail endpoint. The backend loads `purchases`, identifies `purchase_type`, and then reads exactly one of `digital_purchase_details`, `physical_purchase_details`, or `subscription_purchase_details`. No `/digital-details`, `/physical-details`, or `/subscription-details` API contract is exposed.

Frontend purchase detail pages consume this response to render type-specific presentation components. Digital details render code issuance and redemption state, physical details render delivery and tracking state, and subscription details render billing-cycle state. Prepared or issued refund state is rendered in product-specific `Return Details` sections. For subscriptions, clients should show prepared cancellation state as auto-renewal off, days used in the billing cycle, and `Subscription Cancelled`; issued subscription refunds also show cancel date, amount, and the expected refund window. Clients must treat this as display-only state returned by the backend and must not infer cancellation, issuance, or eligibility independently.

## GET /api/purchases/{purchase_id}/refund/eligibility

Purpose
Return backend-evaluated refund workflow state for one purchase without mutating refund lifecycle state.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body

```json
{
  "success": true,
  "data": {
    "purchase_id": "40000000-0000-4000-8000-000000000001",
    "purchase_type": "digital",
    "can_enter_refund_workflow": true,
    "can_prepare_refund": true,
    "can_issue_funds": false,
    "refund_stage": "eligible",
    "required_action": "invalidate_code",
    "refundable_amount_cents": 4500,
    "refund_outcome": "full",
    "reasons": [],
    "policy_facts": {
      "purchase_status": "completed",
      "refund_window_expires_at": "2026-07-05T14:30:00Z",
      "evaluated_at": "2026-07-03T14:30:00Z",
      "refund_requested_at": null,
      "refunded_at": null,
      "refund_amount_cents": null,
      "refund_outcome": null,
      "code_redeemed": false,
      "code_invalidated_at": null,
      "refund_lock_reason": null
    }
  },
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
PURCHASE_NOT_FOUND
PURCHASE_DETAILS_NOT_FOUND
DATABASE_NOT_CONFIGURED

Notes
This endpoint loads the purchase and matching detail row through backend repositories, then evaluates deterministic refund workflow policy in backend services. It does not let clients submit eligibility, lifecycle state, refund outcome, refund deadlines, or refund amounts.

`can_enter_refund_workflow` means the purchase is eligible to begin refund handling. `can_prepare_refund` means the backend can perform the required product-specific preparation step. `can_issue_funds` means mock fund release is allowed.

`refund_stage` is one of `blocked`, `eligible`, `prepared`, or `issued`.

`required_action` is one of `none`, `request_refund`, `invalidate_code`, `generate_return_label`, `cancel_subscription`, `await_carrier_acceptance`, or `issue_funds`.

`refund_outcome` is one of `none`, `full`, or `prorated`.

## POST /api/purchases/{purchase_id}/refund/request

Purpose
Prepare a purchase for refund without issuing funds.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body
Standard response containing the updated refund workflow state.

Possible Error Codes
PURCHASE_NOT_FOUND
PURCHASE_DETAILS_NOT_FOUND
REFUND_PREPARATION_NOT_ALLOWED
DATABASE_NOT_CONFIGURED

Notes
This endpoint performs type-specific preparation only. Physical purchases generate a simulated return barcode flag and label timestamp. Digital purchases invalidate the issued entitlement. Subscription purchases cancel service access and record full or prorated refund mode. The endpoint sets `purchases.status = 'refund_pending'` when preparation succeeds.

Preparation is strict, not idempotent. Duplicate or stale preparation calls return `409 REFUND_PREPARATION_NOT_ALLOWED`.

## POST /api/purchases/{purchase_id}/refund/issue

Purpose
Finalize a prepared mock refund.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body
Standard response containing the updated refund workflow state.

Possible Error Codes
PURCHASE_NOT_FOUND
PURCHASE_DETAILS_NOT_FOUND
REFUND_ISSUANCE_NOT_ALLOWED
DATABASE_NOT_CONFIGURED

Notes
Fund issuance requires prepared state. This endpoint does not perform preparation implicitly. On success it sets `purchases.status = 'refunded'`, `refunded_at`, `refund_amount_cents`, and `refund_outcome`. The issued amount and outcome come from the pre-mutation policy decision and are not recomputed after the status changes to `refunded`.

Issuance is strict, not idempotent. Duplicate or stale issue calls return `409 REFUND_ISSUANCE_NOT_ALLOWED`.

## POST /api/purchases/{purchase_id}/digital/redeem-code

Purpose
Redeem a digital issued code for future frontend simulation.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body
Standard response containing the updated purchase detail payload.

Possible Error Codes
PURCHASE_NOT_FOUND
PURCHASE_DETAILS_NOT_FOUND
CODE_REDEMPTION_NOT_ALLOWED
DATABASE_NOT_CONFIGURED

Notes
Redemption is rejected if the code is already redeemed, already invalidated, or the purchase is in `refund_pending`, `refunded`, or `cancelled` state. On success it sets `code_redeemed = true`, `code_redeemed_at = now`, and `purchases.status = 'redeemed'`.

Redemption is strict, not idempotent. Duplicate or stale redemption calls return `409 CODE_REDEMPTION_NOT_ALLOWED`.

## POST /api/purchases/{purchase_id}/physical/confirm-carrier-acceptance

Purpose
Confirm that a physical return package has been accepted by the carrier.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body
None.

Response Body
Standard response containing the updated refund workflow state.

Possible Error Codes
PURCHASE_NOT_FOUND
PURCHASE_DETAILS_NOT_FOUND
CARRIER_ACCEPTANCE_NOT_ALLOWED
DATABASE_NOT_CONFIGURED

Notes
Carrier acceptance is allowed only for a physical purchase in prepared return state. On success it sets `return_status = 'accepted_by_carrier'` and `accepted_by_carrier_at = now`.

Carrier acceptance is strict, not idempotent. Duplicate or stale carrier-confirmation calls return `409 CARRIER_ACCEPTANCE_NOT_ALLOWED`.

---

# Planned Refund API Contract

Refund API endpoints follow the embedded-detail-table architecture and model refund handling as a staged workflow:

```text
eligibility -> preparation -> issuance
```

The frontend may request workflow actions, but backend services remain authoritative for whether each action is allowed.

## Refund Workflow Read Contract

Refund read endpoints should load `purchases` and the matching purchase detail record, then return backend-evaluated workflow state:

```json
{
  "purchase_id": "...",
  "purchase_type": "physical",
  "can_enter_refund_workflow": true,
  "can_prepare_refund": true,
  "can_issue_funds": false,
  "refund_stage": "eligible",
  "required_action": "generate_return_label",
  "refundable_amount_cents": 0,
  "refund_outcome": "none",
  "reasons": [],
  "policy_facts": {
    "refund_requested_at": null,
    "refunded_at": null,
    "refund_amount_cents": null,
    "refund_outcome": null
  }
}
```

The workflow fields mean:

* `can_enter_refund_workflow`: policy allows the purchase to begin refund handling.
* `can_prepare_refund`: backend can perform the required product-specific preparation step.
* `can_issue_funds`: backend can finalize the mock refund.
* `refund_stage`: current evaluated stage, one of `blocked`, `eligible`, `prepared`, or `issued`.
* `required_action`: next backend action, such as `generate_return_label`, `invalidate_code`, `cancel_subscription`, `await_carrier_acceptance`, or `issue_funds`.

## Refund Preparation Contract

`POST /api/purchases/{purchase_id}/refund/request` prepares the purchase for refund. It must not issue funds.

Preparation always follows this flow:

1. Load the purchase.
2. Load the matching purchase detail record.
3. Evaluate whether the purchase can enter refund workflow.
4. Evaluate whether the product-specific preparation step is allowed.
5. Apply only the preparation mutation for the purchase type.
6. Set `purchases.status = 'refund_pending'` and `refund_requested_at = now`.
7. Return updated workflow state.

Preparation updates must be guarded by expected database state. If either the detail-row update or purchase-row update affects anything other than one row, the transaction rolls back and the endpoint returns `409 REFUND_PREPARATION_NOT_ALLOWED`.

Preparation behavior by purchase type:

* Physical: set `return_status = 'requested'`, `return_requested_at = now`, `return_barcode_generated = true`, and `return_label_created_at = now`.
* Digital: set `code_invalidated_at = now`.
* Subscription: set `cancelled_at = now`, `service_ended_at = now`, `auto_renew = false`, and `refund_proration_mode = 'full'` or `'prorated'`.

## Refund Issuance Contract

`POST /api/purchases/{purchase_id}/refund/issue` finalizes a prepared mock refund.

Issuance always follows this flow:

1. Load the purchase.
2. Load the matching purchase detail record.
3. Verify the purchase is already prepared.
4. Verify product-specific issue gates.
5. Persist `purchases.status = 'refunded'`, `refunded_at`, `refund_amount_cents`, and `refund_outcome` from the pre-mutation policy decision.
6. Return issued workflow state using the same pre-mutation amount and outcome.

Issuance must not perform preparation implicitly. Digital and subscription purchases still require the request/preparation endpoint before issue, even when their preparation can happen immediately.

Issuance updates must be guarded by `purchases.status = 'refund_pending'`. Duplicate issue calls return `409 REFUND_ISSUANCE_NOT_ALLOWED`.

Issue gates by purchase type:

* Physical: requires prepared return state and `accepted_by_carrier_at`.
* Digital: requires prepared state and `code_invalidated_at`.
* Subscription: requires prepared cancellation state and recorded `refund_proration_mode`.

## Simulation Utility Contract

Some lifecycle events are simulated for frontend workflows:

* `POST /api/purchases/{purchase_id}/digital/redeem-code`
  * Marks an issued code as redeemed.
  * Rejects redemption when the code is already redeemed, invalidated, refund pending, refunded, or cancelled.
  * Sets `purchases.status = 'redeemed'`.
  * Duplicate or stale redemption calls return `409 CODE_REDEMPTION_NOT_ALLOWED`.

* `POST /api/purchases/{purchase_id}/physical/confirm-carrier-acceptance`
  * Marks a prepared physical return as accepted by the carrier.
  * Sets `return_status = 'accepted_by_carrier'` and `accepted_by_carrier_at = now`.
  * Enables fund issuance when the rest of policy still permits it.
  * Duplicate or stale carrier-confirmation calls return `409 CARRIER_ACCEPTANCE_NOT_ALLOWED`.

## Client Authority Boundary

Clients should never send fields such as `eligible`, `can_issue_funds`, `refunded`, `refund_pending`, `refund_outcome`, `refundable_amount_cents`, or model-generated policy conclusions as authoritative input. Those values are computed inside backend services.

Clients should also never send database-derived refund deadline values. Deadline fields are computed by PostgreSQL triggers from persisted purchase/detail-table state.

Clients should treat refund mutations as strict commands. Retrying a command after it already succeeded may return a workflow conflict rather than the current state.

No API contract should require or expose a standalone `refunds` table. Refund lifecycle state remains embedded in `digital_purchase_details`, `physical_purchase_details`, and `subscription_purchase_details`, with `purchases.status` serving only as a workflow summary.

## Frontend Refund Proxy Routes

The Next.js frontend may expose same-origin route handlers that proxy browser-initiated refund workflow calls to the FastAPI backend:

* `GET /api/purchases/{purchase_id}/refund/eligibility`
* `POST /api/purchases/{purchase_id}/refund/request`
* `POST /api/purchases/{purchase_id}/refund/issue`
* `POST /api/purchases/{purchase_id}/physical/confirm-carrier-acceptance`

These routes exist to keep browser requests same-origin during local development. They must not evaluate refund policy, mutate workflow state independently, or transform backend decisions beyond forwarding the backend response body and status. FastAPI remains authoritative for refund eligibility, preparation, carrier acceptance, and fund issuance.

## Frontend Chat Proxy Route

The Next.js frontend exposes a same-origin route handler for browser-initiated chat requests:

* `POST /api/chat`

This route forwards the request body to the FastAPI `POST /api/chat` endpoint and returns the backend response body and status. It must not call OpenAI, execute LangGraph, interpret assistant behavior, inspect purchase data, evaluate policy, or mutate workflow state. If FastAPI is unavailable, it returns `503 BACKEND_UNAVAILABLE`.

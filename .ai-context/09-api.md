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

## GET /health/model

Purpose
Verify that the backend can complete a minimal OpenAI model handshake using the configured API key and model.

Authentication Requirements
None.

Request Body
None.

Success Response Body

```json
{
  "success": true,
  "data": {
    "provider": "openai",
    "configured": true,
    "connected": true,
    "model": "gpt-5.4-mini"
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
    "provider": "openai",
    "configured": false,
    "connected": false,
    "model": "gpt-5.4-mini"
  },
  "error": {
    "code": "MODEL_NOT_CONFIGURED",
    "message": "OPENAI_API_KEY is not configured."
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
    "code": "MODEL_CONNECTION_FAILED",
    "message": "OpenAI model handshake failed."
  },
  "meta": {
    "timestamp": "..."
  }
}
```

Possible Error Codes
MODEL_NOT_CONFIGURED
MODEL_CONNECTION_FAILED

Notes
This endpoint validates OpenAI model connectivity only. It performs a minimal non-tool model call and does not execute LangGraph, call backend AI tools, inspect purchase data, evaluate policy, or mutate business state. It returns HTTP `503 Service Unavailable` when the API key is missing or the model handshake fails.

## POST /api/chat

Purpose
Accept a text chat message from the frontend help panel and return a LangGraph-backed AI response for purchase-history, refund-policy, refund-eligibility, and confirmation-gated refund workflow questions.

Authentication Requirements
None. Authentication remains mocked for this project scope.

Request Body

```json
{
  "message": "How many digital purchases have I made?",
  "customer_id": "10000000-0000-4000-8000-000000000001",
  "purchase_id": "40000000-0000-4000-8000-000000000001",
  "page_context": {
    "surface": "purchase_detail",
    "purchase_id": "40000000-0000-4000-8000-000000000001"
  },
  "conversation_state": {
    "selected_purchase_type": "digital",
    "selected_product": null,
    "selected_purchase_id": null,
    "selected_purchase_ids": [],
    "selected_scope_label": null,
    "selected_policy_scope": null,
    "selected_date_range": null,
    "selected_refund_purchase_ids": [],
    "selected_refund_context": null,
    "active_refund_context": null,
    "active_result_set": null,
    "active_workflow": null,
    "pending_refund_action": null,
    "current_page": null
  }
}
```

`message` is required to contain non-empty text after trimming whitespace. `customer_id` identifies the active mock customer for purchase-history, refund-eligibility, and confirmed refund workflow execution. General refund policy lookup may run without `customer_id` because it is not account-specific. `purchase_id` remains an optional legacy page hint from purchase detail routes. `page_context` is the current screen reference and should include only the active surface, either `purchase_history` or `purchase_detail`, plus the active detail `purchase_id` when present. It must not include full rendered page content. `conversation_state` is an optional compact client-carried state object from the previous chat response. It may include selected purchase type, selected product, selected purchase id, selected purchase ids, selected scope label, selected policy scope, selected date range, selected refund purchase ids, selected refund context, active refund context, active result set, active workflow, pending refund action, and the backend-resolved current page reference. These fields are context hints for the local mock-auth scope, not production authentication or authorization inputs.

Success Response Body

```json
{
  "success": true,
  "data": {
    "message": {
      "role": "assistant",
      "content": "You made 2 digital purchases totaling $75.00."
    },
    "model": "gpt-5.4-mini",
    "graph_ready": true,
    "conversation_state": {
      "selected_purchase_type": "digital",
      "selected_product": null,
      "selected_purchase_id": null,
      "selected_purchase_ids": [
        "40000000-0000-4000-8000-000000000001",
        "40000000-0000-4000-8000-000000000002"
      ],
      "selected_scope_label": "your digital purchases",
      "selected_policy_scope": null,
      "selected_date_range": null,
      "selected_refund_purchase_ids": [],
      "selected_refund_context": null,
      "active_refund_context": null,
      "active_result_set": {
        "type": "digital",
        "purchase_ids": [
          "40000000-0000-4000-8000-000000000001",
          "40000000-0000-4000-8000-000000000002"
        ],
        "sort": "purchased_at_asc",
        "label": "your digital purchases"
      },
      "active_workflow": {
        "kind": "account_fact",
        "object": "purchase_type",
        "object_label": "digital purchases",
        "operation": "count",
        "reason": "purchase_type_query"
      },
      "pending_refund_action": null,
      "current_page": {
        "surface": "purchase_detail",
        "purchase": {
          "id": "40000000-0000-4000-8000-000000000001",
          "product_name": "Design Template Pack",
          "sku": "DIG-TEMPLATE-001",
          "order_number": "RAI-10001",
          "purchase_type": "digital"
        }
      }
    },
    "side_effects": []
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
`side_effects` is usually an empty list. After a confirmed refund mutation succeeds and the backend verifies the persisted workflow state, the chat response includes a `purchase_data_changed` side effect with `customer_id`, affected `purchase_ids`, and reason `refund_mutation_completed`. The frontend uses this as a lightweight refetch signal so purchase and refund workflow data update without a browser page reload or chat state reset.

This endpoint runs the AI Agent Integration graph. The graph asks the configured OpenAI model to request supported read-only tools, executes valid tool calls through backend services, and asks the model to answer from available tool context. Supported OpenAI-facing tools currently include `get_customer_purchase_history`, `get_purchase_count_by_amount_threshold`, `get_purchase_history_by_date_range`, `get_refund_policy`, and `get_refund_eligibility`; those tools remain read-only. If the model returns malformed pseudo-tool text instead of a real tool call, the backend logs `model.invalid_tool_output` and ignores that text as invalid model output. Before honoring any model-requested tool or refund workflow request, deterministic backend routing resolves a conversation object and operation, then maps that pair to account-fact, refund-policy, refund-eligibility, refund-mutation, or clarification workflows. Explicit named product references take precedence over scoped state, while demonstrative phrases such as "these products", "those purchases", "these types of products", "them", or "they" resolve to the active purchase/result set before they can be treated as unresolved literal product names. If the model does not request a supported tool, deterministic backend fallback routing executes the narrowest supported account, policy, or eligibility tool and skips tools for off-domain messages. The graph returns compact `conversation_state` so follow-up policy and eligibility questions such as "those purchases" can resolve from selected state, and explicit product follow-ups such as "what about the Developer Toolkit?" can escape the narrowed selected set and resolve through exact, normalized, partial, fuzzy, SKU, or order-number matching against the active customer's full purchase rows. After `get_refund_eligibility` resolves exactly one purchase, the graph stores `active_refund_context` with the evaluated purchase id, product name, purchase type, eligibility, stage, next action, reason codes, and the expected canonical confirmation command. Digital purchases require `Confirm invalidate code and issue refund`, subscriptions require `Confirm cancel and issue refund`, and physical purchases require `Confirm start return and issue label`. Follow-up return workflow continuations such as "generate the return label" resolve only from that active context but do not mutate after the command boundary has been issued. A mutation request such as "start the refund" or "close out the refund" never mutates on the first request: the backend validates that exactly one purchase is resolved, confirms the current deterministic workflow allows the requested `request_refund` or `issue_refund` action, stores command-ready `active_refund_context`, and asks the customer for the canonical command. Only the expected canonical command creates the internal `pending_refund_action` and executes the backend `ApplicationService.request_refund` or `ApplicationService.issue_refund` command. Generic replies such as "yes", "proceed", "do it", or "continue" do not mutate refund state. The graph injects only compact model-visible context into tool-selection and final-response requests: selected purchase type, product, purchase id, selected scope label, selected id counts with short ids, active result set label/count, policy scope, refund context, active refund context, pending refund action, current purchase-detail reference, summarized tool data, and blocked-action context. It must not send the full prior transcript or full rendered page content. When `active_result_set` is the final response's primary answer source, the model request hydrates the selected ids from the latest purchase-history tool result or backend service into safe purchase display fields; raw full-history tool results remain available as raw context but are not framed as the primary source. `conversation_state.active_result_set` itself remains ID-only plus metadata. Named product references must resolve unambiguously to an actual purchase before the graph may answer product-specific policy or eligibility questions. If no purchase match is found or multiple product-name matches are plausible, the graph must not infer purchase type, must not call `get_refund_policy` or `get_refund_eligibility`, and must return a concise clarification asking for product name, order number, SKU, or purchase date. Aggregate and list results that produce `selected_purchase_ids` become the active scope for follow-up resolution, including purchase-type groups, amount-threshold groups, date ranges, and other filtered purchase-history results. Those results also store `selected_scope_label` and `active_result_set` for customer-safe follow-up phrasing such as `your subscriptions`, `purchases from May 2026`, or `purchases over $100.00`. Scoped ranking follow-ups that use "one", "that one", "those", "last one", "first one", "latest", "most recent", "newest", "oldest", "earliest", "cheapest", or "most expensive" resolve inside the active selected set first when that selected set exists. "Oldest", "earliest", and "first" mean the lowest `purchased_at`; "latest", "most recent", "newest", and "last one" mean the highest `purchased_at`; "cheapest" and "most expensive" rank by `amount_cents`. The graph falls back to global ranked purchase history only when no selected set exists. Ranking-only follow-ups are account-fact questions, not refund-policy or refund-eligibility questions. The graph must not call `get_refund_policy` or `get_refund_eligibility` for a ranking-only follow-up unless the user explicitly asks about refund policy, return policy, cancellation rules, refundability, eligibility, approval, or the refund process. Whenever the backend resolves exactly one concrete purchase, it updates selected purchase id, product, and purchase type from the backend row before future turns. The graph also resolves `page_context` for purchase detail pages into a compact current-page reference containing only purchase id, product name, sku, order number, and purchase type. That current-page reference can ground "this product", "this item", "this purchase", and "this order" policy and eligibility questions without sending full page content to the model. Account-fact responses are blocked unless an authoritative tool result exists; the backend returns a safe assistant response instead of allowing a factual hallucination. Refund policy explanations are allowed only from the backend policy catalog returned by `get_refund_policy`. Refund eligibility explanations are allowed only from backend refund workflow decisions returned by `get_refund_eligibility`; the model must not infer, override, or calculate eligibility independently. Refund workflow mutations run only through deterministic backend services after the canonical confirmation command; the model must not claim a refund was prepared or issued unless backend mutation context says the action completed. Money remains stored and compared in cents; dollar-denominated user input is converted to cents at the chat boundary, and tool payloads may include derived dollar display strings for model explanation. Date filters resolve in the customer timezone before querying, use Sunday-through-Saturday business weeks for relative week phrases, convert inclusive local dates to half-open UTC timestamp ranges for purchase filtering, and include derived date display strings plus the resolved local date_range in tool output. If no customer context is available for account-specific purchase facts, eligibility lookup, or confirmed workflow mutation, the assistant asks the user to load a mock customer. If OpenAI is unavailable or `OPENAI_API_KEY` is missing, the endpoint returns a successful chat envelope with an assistant-level unavailable message. The model is instructed to return plain standard text without Markdown formatting and must not expose backend terms such as selected context, selected set, state, tool, resolver, purchase ids, node, or graph in customer-facing answers; the backend also guards final responses against those terms. The model should keep the conversation grounded in the customer's account, account history, purchases, orders, account activity, refund policy, and refund flows. Unrelated topics should receive a brief graceful redirect back to supported account topics. The backend emits sequential trace events for route receipt, graph start, model request packages, workflow classification/context/execution, confirmation command generation/receipt/verification/rejection, mutation attempts, workflow conflicts, mutation outcomes, tool-call selections, invalid model output, optional tool execution or tool skipping, blocked response decisions, tool results, final model response generation, and route response return. Structured application log records retain each trace event's step number, source file, source line, message, and structured data payload for tests and future audit surfaces. Console output renders those same events as concise human-readable step summaries so local development logs do not dump full nested prompt, tool, or response payloads. Console summaries include compact model context such as selected conversation state, current page or resolved page reference, intent flags, active-result-set previews, pending refund action summaries, summarized raw tool data made available to the model, mutation outcomes, confirmation command state, and blocked-action reasons. These logs expose the observable orchestration path and tool usage; they do not expose private model hidden reasoning. The endpoint must not inspect purchase data outside backend services, capture voice input, or persist conversation logs.

Customer-facing assistant content must refer to overall refund handling as "the refund process" and, for physical purchases, the return-label and carrier phase as "the return process." It must not expose internal terms such as workflow, mutation, backend step, persisted state, orchestration, `issue_funds`, `invalidate_code`, `cancel_subscription`, `required_action`, selected context, selected set, state, tool, resolver, purchase ids, node, or graph.

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

This route forwards the request body to the FastAPI `POST /api/chat` endpoint and returns the backend response body and status. It must not call OpenAI, execute LangGraph, interpret assistant behavior, inspect purchase data, evaluate policy, or mutate workflow state. If FastAPI is unavailable, it returns `503 BACKEND_UNAVAILABLE`. Browser chat requests should include `customer_id` from `/user-home?customerId=...` or the selected mock customer session storage when available.

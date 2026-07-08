# 09-api.md

# API Contracts

## Purpose

This document defines the HTTP contract between the Next.js frontend and FastAPI backend.

Implementation source:

* FastAPI routes: `apps/api/src/refunds_ai_api/routes/`
* FastAPI schemas: `apps/api/src/refunds_ai_api/schemas/`
* Frontend API client: `apps/web/src/lib/application-api.ts`
* Frontend proxy routes: `apps/web/src/app/api/`

## API Principles

* Frontend code communicates through documented HTTP endpoints.
* FastAPI remains authoritative for business behavior.
* The frontend must not access Supabase or OpenAI directly.
* Response bodies use the standard envelope.
* Clients must not submit authoritative refund eligibility, lifecycle, amount, outcome, or deadline values.
* Backend implementation details should stay behind route contracts.

## Standard Response Envelope

Success:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "timestamp": "..."
  }
}
```

Failure:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message."
  },
  "meta": {
    "timestamp": "..."
  }
}
```

## Implemented FastAPI Endpoints

| Method | Route | Service path | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | `routes/health.py` | Process readiness envelope. |
| `GET` | `/health/database` | `services/database.py` | Supabase PostgreSQL handshake. |
| `GET` | `/health/model` | `services/model_health.py` | Minimal OpenAI model handshake. |
| `POST` | `/api/chat` | `services/ai_chat/` | AI chat orchestration. |
| `GET` | `/api/users/mock` | `ApplicationService.list_mock_users` | Selectable mock users. |
| `GET` | `/api/users/{user_id}` | `ApplicationService.get_user` | One mock user with roles. |
| `GET` | `/api/users/{user_id}/purchases` | `ApplicationService.list_user_purchases` | Purchase history rows. |
| `GET` | `/api/purchases/{purchase_id}/details` | `ApplicationService.get_purchase_detail` | Backend-resolved type-specific purchase details. |
| `GET` | `/api/purchases/{purchase_id}/refund/eligibility` | `ApplicationService.get_refund_workflow` | Read-only refund workflow decision. |
| `POST` | `/api/purchases/{purchase_id}/refund/request` | `ApplicationService.request_refund` | Prepare refund without issuing funds. |
| `POST` | `/api/purchases/{purchase_id}/refund/issue` | `ApplicationService.issue_refund` | Finalize prepared mock refund. |
| `POST` | `/api/purchases/{purchase_id}/digital/redeem-code` | `ApplicationService.redeem_digital_code` | Simulate digital code redemption. |
| `POST` | `/api/purchases/{purchase_id}/physical/confirm-carrier-acceptance` | `ApplicationService.confirm_carrier_acceptance` | Simulate carrier acceptance. |
| `GET` | `/api/admin/audit/sessions` | `ModelAuditReadService.list_sessions` | List persisted model audit sessions. |
| `GET` | `/api/admin/audit/sessions/{session_id}` | `ModelAuditReadService.get_session` | Read one model audit session summary. |
| `GET` | `/api/admin/audit/sessions/{session_id}/events` | `ModelAuditReadService.list_events` | Read ordered events for one audit session. |
| `GET` | `/api/admin/audit/events/stream` | `ModelAuditReadService.stream_events` | SSE stream for database-broadcast audit events. |

Authentication is currently mocked. These endpoints do not implement production auth.

## Admin Audit Endpoints

The audit schema, writer, graph instrumentation, HTTP read APIs, backend SSE stream,
and frontend admin consumption are implemented for the current text-chat audit surface.

| Method | Route | Status | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/admin/audit/sessions` | Implemented | List historical and active audit sessions. |
| `GET` | `/api/admin/audit/sessions/{session_id}` | Implemented | Read one audit session summary. |
| `GET` | `/api/admin/audit/sessions/{session_id}/events` | Implemented | Read ordered audit events for a session. |
| `GET` | `/api/admin/audit/events/stream` | Implemented | SSE stream for active audit events. |

## Health Endpoints

### `GET /health`

Returns process readiness only.

Data:

* `service`
* `status`

Does not validate database, model, schema, seed data, or business readiness.

### `GET /health/database`

Checks whether `SUPABASE_DB_URL` is configured and whether the backend can run a
non-mutating PostgreSQL handshake.

Data:

* `provider: "supabase-postgres"`
* `configured`
* `connected`

Errors:

* `DATABASE_NOT_CONFIGURED` with HTTP `503`
* `DATABASE_CONNECTION_FAILED` with HTTP `503`

### `GET /health/model`

Checks whether `OPENAI_API_KEY` is configured and whether the backend can perform a
minimal model call.

Data:

* `provider: "openai"`
* `configured`
* `connected`
* `model`

Errors:

* `MODEL_NOT_CONFIGURED` with HTTP `503`
* `MODEL_CONNECTION_FAILED` with HTTP `503`

This endpoint does not run LangGraph or tools.

## User and Purchase Read Endpoints

### `GET /api/users/mock`

Returns selectable mock users.

Data shape:

* `users[]`
  * `id`
  * `first_name`
  * `last_name`
  * `created_at`
  * `display_name`
  * `roles[]` with `key`, `name`

Errors:

* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `GET /api/users/{user_id}`

Returns one mock user with roles.

Data shape:

* `user`
  * `id`
  * `first_name`
  * `last_name`
  * `created_at`
  * `display_name`
  * `roles[]`

Errors:

* `USER_NOT_FOUND` with HTTP `404`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `GET /api/users/{user_id}/purchases`

Returns purchase history for one mock user.

Data shape:

* `purchases[]`
  * `id`
  * `order_number`
  * `purchase_type`
  * `product_name`
  * `sku`
  * `amount_cents`
  * `purchased_at`
  * `status`
  * `details_url`

Notes:

* Backend reads `purchases` joined to `products`.
* `details_url` is generated by `ApplicationService`.
* Clients use one stable detail route rather than type-specific detail endpoints.

Errors:

* `USER_NOT_FOUND` with HTTP `404`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `GET /api/purchases/{purchase_id}/details`

Returns the matching type-specific detail payload for one purchase.

Common data shape:

* `purchase_id`
* `purchase_type`
* `details`

Digital detail fields:

* `issued_code`
* `code_redeemed`
* `code_redeemed_at`
* `code_invalidated_at`
* `code_delivered_at`
* `refund_window_expires_at`
* `refund_lock_reason`

Physical detail fields:

* `scheduled_delivery_at`
* `delivered_at`
* `return_status`
* `carrier`
* `tracking_number`
* `return_barcode_generated`
* `return_label_created_at`
* `accepted_by_carrier_at`
* `return_requested_at`
* `return_authorized_at`
* `return_received_at`
* `return_rejected_at`
* `return_rejection_reason`
* `refund_window_expires_at`

Subscription detail fields:

* `period_start`
* `period_end`
* `cancelled_at`
* `service_ended_at`
* `auto_renew`
* `refund_proration_mode`
* `full_refund_window_expires_at`
* `refund_window_expires_at`

Errors:

* `PURCHASE_NOT_FOUND` with HTTP `404`
* `PURCHASE_DETAILS_NOT_FOUND` with HTTP `404`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

## Refund Workflow Endpoints

### Shared Workflow Response

Refund workflow endpoints return the backend decision shape:

* `purchase_id`
* `purchase_type`
* `can_enter_refund_workflow`
* `can_prepare_refund`
* `can_issue_funds`
* `refund_stage`: `blocked`, `eligible`, `prepared`, or `issued`
* `required_action`: `none`, `request_refund`, `invalidate_code`, `generate_return_label`, `cancel_subscription`, `await_carrier_acceptance`, or `issue_funds`
* `refundable_amount_cents`
* `refund_outcome`: `none`, `full`, or `prorated`
* `reasons[]`
* `policy_facts`

Clients treat this as display/control state only.

### `GET /api/purchases/{purchase_id}/refund/eligibility`

Returns a read-only refund workflow decision. It does not mutate state.

Errors:

* `PURCHASE_NOT_FOUND` with HTTP `404`
* `PURCHASE_DETAILS_NOT_FOUND` with HTTP `404`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `POST /api/purchases/{purchase_id}/refund/request`

Prepares a refund. It does not issue funds.

Preparation behavior:

| Type | Mutation |
| --- | --- |
| Digital | Set `digital_purchase_details.code_invalidated_at`; set purchase `status = 'refund_pending'`. |
| Physical | Set return requested, generated barcode, label timestamp; set purchase `status = 'refund_pending'`. |
| Subscription | Set cancellation/service end, disable auto-renew, set `refund_proration_mode`; set purchase `status = 'refund_pending'`. |

Errors:

* `PURCHASE_NOT_FOUND` with HTTP `404`
* `PURCHASE_DETAILS_NOT_FOUND` with HTTP `404`
* `REFUND_PREPARATION_NOT_ALLOWED` with HTTP `409`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `POST /api/purchases/{purchase_id}/refund/issue`

Issues a prepared mock refund. It must not perform preparation implicitly.

On success, the backend sets final purchase facts:

* `status = 'refunded'`
* `refunded_at`
* `refund_amount_cents`
* `refund_outcome`

Errors:

* `PURCHASE_NOT_FOUND` with HTTP `404`
* `PURCHASE_DETAILS_NOT_FOUND` with HTTP `404`
* `REFUND_ISSUANCE_NOT_ALLOWED` with HTTP `409`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `POST /api/purchases/{purchase_id}/digital/redeem-code`

Simulates digital entitlement redemption.

Allowed only when the purchase is digital, completed, not refund pending/refunded/cancelled,
not already redeemed, and not invalidated.

On success:

* `digital_purchase_details.code_redeemed = true`
* `digital_purchase_details.code_redeemed_at = now`
* `purchases.status = 'redeemed'`

Errors:

* `PURCHASE_NOT_FOUND` with HTTP `404`
* `PURCHASE_DETAILS_NOT_FOUND` with HTTP `404`
* `CODE_REDEMPTION_NOT_ALLOWED` with HTTP `409`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `POST /api/purchases/{purchase_id}/physical/confirm-carrier-acceptance`

Simulates the carrier accepting a prepared physical return.

Allowed only when the purchase is physical, `purchases.status = 'refund_pending'`,
`return_status = 'requested'`, and no prior carrier acceptance exists.

On success:

* `physical_purchase_details.return_status = 'accepted_by_carrier'`
* `physical_purchase_details.accepted_by_carrier_at = now`

Errors:

* `PURCHASE_NOT_FOUND` with HTTP `404`
* `PURCHASE_DETAILS_NOT_FOUND` with HTTP `404`
* `CARRIER_ACCEPTANCE_NOT_ALLOWED` with HTTP `409`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

## Chat Endpoint

### `POST /api/chat`

Runs the AI chat graph for purchase-history, refund-policy, refund-eligibility, and
confirmation-gated refund process questions.

Request fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `message` | Yes | Customer text. Blank or whitespace-only messages return `INVALID_CHAT_MESSAGE`. |
| `customer_id` | Account-specific requests | Active mock customer id supplied by the page/client. The model must not choose it. |
| `purchase_id` | No | Legacy page hint from purchase detail routes. |
| `page_context` | No | Compact current screen reference: `purchase_history` or `purchase_detail` plus purchase id. |
| `conversation_state` | No | Compact state returned by the previous chat response. |

Accepted `conversation_state` fields:

* `selected_purchase_type`
* `selected_product`
* `selected_purchase_id`
* `selected_purchase_ids`
* `selected_scope_label`
* `selected_policy_scope`
* `selected_date_range`
* `selected_refund_purchase_ids`
* `selected_refund_context`
* `active_refund_context`
* `active_result_set`
* `active_purchase`
* `active_workflow`
* `pending_refund_action`
* `customer_explanation_context`
* `entity_extraction_result`
* `current_page`

`customer_explanation_context` is backend-normalized customer-facing explanation
context for denied refund process actions. It describes what the system shows, the
policy requirement, why the action cannot proceed, and any next step. It is not client
authority to mutate refund state.

`entity_extraction_result` records the last turn's separated intent and entity
classification, rejected generic/action candidates, and the structured context source
used for contextual references. Clients must treat it as diagnostic routing state, not
purchase authority.

Workflow context audit events also expose a normalized `current_message_entity` plus
the previous scope, scope used, candidate matches, selected purchase id, and resolution
reason. Named products from the current message resolve against full purchase history
and override stale active result-set scope.

Each `POST /api/chat` request creates one audit session. Session totals cover every
workflow step, model call, and backend tool operation caused by that single user
prompt. A follow-up request creates a new session even when its model payload includes
structured state from the previous turn. Model-request audit payloads distinguish
`user_prompt` from `system_instructions`, `additional_context`, available tools, and
compact backend model context. Provider-reported token usage and measured per-call
latency are stored on dedicated model lifecycle events and aggregated by the audit read
service as authoritative model totals. Model lifecycle events also expose diagnostic
estimated input/output token counts, tokenizer name, and component breakdowns so prompt
budget changes can be reviewed before provider totals alone explain the cause.
For final-response calls, the compact backend model context is a request-specific
projection of deterministic tool results. Lifecycle metadata includes `request_category`,
`projection_reason`, `raw_context_tokens`, `projected_context_tokens`,
`token_savings_estimated`, `prompt_module_tokens`, `tool_schema_tokens`,
`tool_result_tokens`, and `conversation_state_tokens` when available.

Backend tools emit paired `TOOL_STARTED` and `TOOL_COMPLETED` timeline events with a
shared `tool_call_id`. Tool History and session totals consolidate those records by
that id, so one backend invocation counts once. Completion records carry source,
workflow, operation, latency, input/output summaries, backend category, and available
customer or purchase identifiers. Tool lifecycle records also carry estimated input
and output token counts for the serialized backend arguments/results shown to the
workflow. Backend tools do not contribute provider model token usage unless they invoke
a model internally.

Response data:

* `message.role = "assistant"`
* `message.content`
* `model`
* `graph_ready`
* `conversation_state`
* `side_effects[]`

Possible errors:

* `INVALID_CHAT_MESSAGE` with HTTP `400`

If OpenAI is unavailable or not configured, the route can still return a successful
chat envelope with an assistant-level unavailable message.

### Chat Side Effects

`side_effects` is usually empty.

After a confirmed refund process mutation succeeds, the response may include:

* `type: "purchase_data_changed"`
* `customer_id`
* `purchase_ids`
* `reason: "refund_mutation_completed"`

The frontend uses this as a refetch signal and must not treat it as authority beyond
refreshing backend data.

### Chat Authority Rules

The endpoint may use these OpenAI-facing read-only tools:

* `validate_customer_account`
* `get_customer_purchase_history`
* `get_purchase_history_by_date_range`
* `get_purchase_count_by_amount_threshold`
* `get_refund_policy`
* `get_refund_eligibility`

The backend narrows this available schema list per request before tool selection. For
example, refund policy requests expose only `get_refund_policy`, refund eligibility
requests expose only `get_refund_eligibility`, and ordinary purchase-history facts
expose only the matching account-fact read tool. Off-domain, fallback, and refund
mutation flows expose no read-only tool schemas and may skip the tool-selection model
call entirely.

Refund process mutations are not OpenAI-facing tools. They execute only when:

* Backend resolution identifies exactly one purchase.
* Prior state contains an active refund context with the expected canonical command.
* The backend confirmation validator matches the current customer message to that
  command after deterministic normalization.
* The validator persists confirmation consent for the active customer, purchase,
  purchase type, expected command, exact received message, and grant timestamp.
* Mutation execution reloads persisted confirmation and verifies grant, match,
  customer, purchase, expected command, unused scope, and current workflow state.
* Current backend workflow state allows the requested atomic action.

Mock authentication remains intentionally simple: the request supplies the active
`customer_id`, and backend ownership checks verify that the target purchase appears in
that customer's purchase rows. The model may read active mock-customer metadata through
`validate_customer_account`, but it does not choose identity or authorize refund actions.

Canonical commands:

| Type | Command |
| --- | --- |
| Digital | `Confirm invalidate code and issue refund` |
| Physical | `Confirm start return and issue label` |
| Subscription | `Confirm cancel and issue refund` |

For digital and subscription purchases, valid persisted confirmation may orchestrate
preparation and issuance in one conversational turn. The backend still executes them
as separate atomic transitions: request, verify prepared state, issue, verify issued
state. For physical purchases, the canonical command prepares the return process only;
fund issuance still requires carrier acceptance.

After a single eligible physical purchase is evaluated and the next action is return
label generation, `conversation_state.pending_refund_action` carries the backend-
resolved purchase id, product name, purchase type, action, required action, and expected
canonical command. This state is not authorization; the matching command must still
pass backend confirmation validation with the active request `customer_id`.

Generic replies such as `yes`, `proceed`, `do it`, or `continue` must not mutate state
at the command boundary.

## Frontend Proxy Contracts

Next.js route handlers proxy browser requests to FastAPI:

| Frontend route | Backend route |
| --- | --- |
| `POST /api/chat` | `POST /api/chat` |
| `GET /api/admin/audit/sessions` | `GET /api/admin/audit/sessions` |
| `GET /api/admin/audit/sessions/{session_id}` | `GET /api/admin/audit/sessions/{session_id}` |
| `GET /api/admin/audit/sessions/{session_id}/events` | `GET /api/admin/audit/sessions/{session_id}/events` |
| `GET /api/admin/audit/events/stream` | `GET /api/admin/audit/events/stream` |
| `GET /api/purchases/{purchase_id}/refund/eligibility` | `GET /api/purchases/{purchase_id}/refund/eligibility` |
| `POST /api/purchases/{purchase_id}/refund/request` | `POST /api/purchases/{purchase_id}/refund/request` |
| `POST /api/purchases/{purchase_id}/refund/issue` | `POST /api/purchases/{purchase_id}/refund/issue` |
| `POST /api/purchases/{purchase_id}/physical/confirm-carrier-acceptance` | `POST /api/purchases/{purchase_id}/physical/confirm-carrier-acceptance` |

Proxy handlers should forward backend status and body. On network failure they return:

* `BACKEND_UNAVAILABLE` with HTTP `503`

## Client Boundary

Clients must not send these fields as authoritative input:

* `eligible`
* `can_prepare_refund`
* `can_issue_funds`
* `refund_pending`
* `refunded`
* `refund_outcome`
* `refundable_amount_cents`
* `refund_window_expires_at`
* model-generated policy conclusions

Clients may request a command. Backend services decide whether the command is allowed.

## Admin Audit API Details

Admin audit reads expose the persisted model audit timeline through standard response
envelopes. Authentication remains mocked for this phase.

### `GET /api/admin/audit/sessions`

Query:

* `limit`: optional, minimum `1`, maximum `100`. When omitted, all stored sessions are returned in reverse chronological order.
* `offset`: optional, default `0`, minimum `0`. Used with `limit` for lazy-loading older sessions.

Data:

* `sessions[]`
  * session identifiers: `id`, `trace_id`, `conversation_id`, `customer_id`, `request_id`
  * model/status fields: `model_name`, `status`
  * metrics: `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms`, `event_count`
  * timestamps: `started_at`, `completed_at`, `created_at`, `updated_at`

### `GET /api/admin/audit/sessions/{session_id}`

Returns one `session` with the same shape as the session list item.

Errors:

* `AUDIT_SESSION_NOT_FOUND` with HTTP `404`
* `DATABASE_NOT_CONFIGURED` with HTTP `503`

### `GET /api/admin/audit/sessions/{session_id}/events`

Returns ordered `events[]` for one session. Event rows include:

* identifiers: `id`, `session_id`, `trace_id`
* ordering and lookup metadata: `sequence_number`, `event_key`, `display_name`, `category`, `description`, `display_order`
* trace facets: `workflow_kind`, `tool_name`, `summary`
* payloads: `input_json`, `output_json`, `metadata_json`
* `created_at`

Event labels and categories come from `model_audit_event_lookup`; frontend code should
not duplicate that mapping.

### `GET /api/admin/audit/events/stream`

Streams database-broadcast audit events as Server-Sent Events.

Query:

* `session_id`: optional. When supplied, only events for that audit session are relayed.

Stream behavior:

* PostgreSQL broadcasts inserted `model_audit_events` rows through the
  `model_audit_events` notification channel.
* SSE event name is `model_audit_event`.
* SSE `data` contains compact event metadata for realtime UI refresh:
  `id`, `session_id`, `trace_id`, `sequence_number`, `event_key`, lookup labels,
  `workflow_kind`, `tool_name`, `summary`, and `created_at`.
* Full event payloads remain available through
  `GET /api/admin/audit/sessions/{session_id}/events`.
* Keepalive comments may be emitted as `: keepalive`.

The admin home screen consumes the stream through a same-origin Next.js proxy route.
Its client-side audit list upserts streamed session updates into the visible list and
lazy-loads older session pages with `limit` and `offset` as the user scrolls.
Admin session detail screens use the same proxy with `session_id` filtering to refresh
the selected session timeline as new events arrive.

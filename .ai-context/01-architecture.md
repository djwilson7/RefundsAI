# 01-architecture.md

# System Architecture

## Layer Model

RefundsAI separates presentation, application services, AI orchestration,
deterministic business policy, and persistent state.

```text
Customer / Administrator
  -> Next.js frontend
  -> FastAPI routes
  -> Application services
  -> Repositories and AI chat graph
  -> Deterministic policy helpers
  -> Supabase PostgreSQL
```

The important boundary is authority: frontend and model output can request or explain
workflow actions, but backend policy and database state decide what is allowed. The
architecture is intentionally hybrid: agentic language handling surrounds a
deterministic transactional core.

## Frontend Surface

Implementation source:

* `apps/web/src/app/layout.tsx`
* `apps/web/src/app/page.tsx`
* `apps/web/src/components/product-landing.tsx`
* `apps/web/src/app/user-home/page.tsx`
* `apps/web/src/app/purchase-details/[purchaseId]/page.tsx`
* `apps/web/src/components/application-help-layer.tsx`
* `apps/web/src/components/purchase-details-placeholder.tsx`
* `apps/web/src/lib/application-api.ts`

Routes:

| Route | Current behavior |
| --- | --- |
| `/` | Product landing page by default; mock authentication when `REFUNDS_AI_DEMO_MODE=false`. |
| `/user-home?customerId=...` | Server-loads customer profile and purchase history. |
| `/admin-home` | Admin home screen with compact model-invocation audit cards loaded from persisted audit sessions and events. |
| `/admin/sessions/[sessionId]` | Admin session detail screen with request identity, process and token metrics, tool purposes/outcomes, and a narrative rendering of every ordered audit event. |
| `/purchase-details/[purchaseId]` | Server-loads purchase detail data and refund workflow state. |

The root layout wraps every page in `ApplicationHelpLayer`. The help layer is only
available on `/user-home` and purchase detail routes.

The product landing branch is presentational. It does not load backend data or expose
chat and refund controls. The root route opts out of static prerendering so selection
can be evaluated at runtime from server-side `REFUNDS_AI_DEMO_MODE`; the public landing
is the default when the variable is absent.

Frontend-only Docker development uses `docker-compose.dev.yml` and the `development`
target in `apps/web/Dockerfile`. That topology runs only the Next.js development server,
bind-mounts `apps/web`, keeps `.next` in a container volume, and uses webpack polling
for reliable Windows bind-mount updates. The standard `docker-compose.yml` remains the
production-style integrated web/API topology.

The customer home screen renders purchase cards from backend data. Before navigating,
each card stores a small session-storage header summary for purchase detail continuity.
The detail route still loads authoritative detail data from FastAPI.

## Purchase Detail Rendering

One backend endpoint, `GET /api/purchases/{purchase_id}/details`, returns the correct
detail row based on `purchases.purchase_type`.

Frontend components then render type-specific sections:

| Purchase type | Detail display |
| --- | --- |
| Digital | Code issuance, redemption, invalidation, and issued refund summary. |
| Physical | Delivery timeline, tracking, return workflow, carrier acceptance, and issued refund summary. |
| Subscription | Billing cycle progress, cancellation state, auto-renew state, days used, and issued refund summary. |

The detail page displays backend state. It must not calculate eligibility, cancellation,
fund issuance, or refund outcome independently.

## Frontend Proxy Routes

Implementation source:

* `apps/web/src/app/api/chat/route.ts`
* `apps/web/src/app/api/purchases/[purchaseId]/refund/eligibility/route.ts`
* `apps/web/src/app/api/purchases/[purchaseId]/refund/request/route.ts`
* `apps/web/src/app/api/purchases/[purchaseId]/refund/issue/route.ts`
* `apps/web/src/app/api/purchases/[purchaseId]/physical/confirm-carrier-acceptance/route.ts`

These handlers keep browser calls same-origin during local development. They forward
requests to FastAPI using `REFUNDS_AI_API_BASE_URL` or `http://localhost:8000`.
They must not evaluate policy, call OpenAI, inspect purchase data, or mutate workflow
state independently.

## Backend Surface

Implementation source:

* `apps/api/src/refunds_ai_api/main.py`
* `apps/api/src/refunds_ai_api/routes/health.py`
* `apps/api/src/refunds_ai_api/routes/application.py`
* `apps/api/src/refunds_ai_api/routes/chat.py`
* `apps/api/src/refunds_ai_api/schemas/`

FastAPI routes are thin. They validate path/body inputs, call services, map known
exceptions to the standard response envelope, and set HTTP status codes.

`ApplicationService` in `apps/api/src/refunds_ai_api/services/application.py` owns the
frontend-ready application behavior:

* Mock user reads.
* Purchase history reads.
* Type-specific purchase detail reads.
* Refund workflow evaluation.
* Guarded refund preparation and issuance.
* Digital code redemption.
* Physical carrier acceptance.

`ApplicationRepository` in `apps/api/src/refunds_ai_api/repositories/application.py`
owns SQL access and guarded writes.

## Refund Workflow Architecture

Implementation source:

* `apps/api/src/refunds_ai_api/services/refund_policy.py`
* `apps/api/src/refunds_ai_api/services/application.py`
* `apps/api/src/refunds_ai_api/repositories/application.py`

Workflow stages:

```text
eligibility -> preparation -> issuance
```

Decision fields returned by the backend:

* `can_enter_refund_workflow`
* `can_prepare_refund`
* `can_issue_funds`
* `refund_stage`
* `required_action`
* `refundable_amount_cents`
* `refund_outcome`
* `reasons`
* `policy_facts`

Preparation is product-specific:

* Digital: invalidate the issued code.
* Physical: request the return and generate simulated label/barcode state.
* Subscription: cancel service access, disable auto-renew, and persist full/prorated mode.

Issuance is shared at the `purchases` level and requires prepared state. It persists
`status = 'refunded'`, `refunded_at`, `refund_amount_cents`, and `refund_outcome`.

Repository mutations are strict. If a guarded SQL update does not affect exactly one
row, the transaction rolls back and the route returns a workflow-specific `409`.

## AI Chat Architecture

Implementation source:

* `apps/api/src/refunds_ai_api/services/ai_chat/service.py`
* `apps/api/src/refunds_ai_api/services/ai_chat/graph.py`
* `apps/api/src/refunds_ai_api/services/ai_chat/nodes/`
* `apps/api/src/refunds_ai_api/services/ai_chat/workflows/`
* `apps/api/src/refunds_ai_api/services/ai_chat/resolvers/`
* `apps/api/src/refunds_ai_api/services/ai_chat/trace/`
* `apps/api/src/refunds_ai_api/services/ai_chat/workflows/refund_mutation/`
* `apps/api/src/refunds_ai_api/services/ai_chat/tools.py`
* `apps/api/src/refunds_ai_api/services/ai_chat/prompts.py`
* `apps/api/src/refunds_ai_api/services/ai_chat/state.py`

The graph shape is intentionally small:

```text
validate_context
  -> request_tool_call
  -> execute_tools
  -> generate_final_response
```

The heavy lifting happens before tool execution:

1. Normalize compact page and conversation state.
2. Resolve the conversation object, such as page purchase, named product, active result set, date range, or amount threshold.
3. Resolve the requested operation, such as count, list, policy, eligibility, or refund start.
4. Use the object-operation lookup table to select a workflow family.
5. Resolve backend context and execute the narrowest read tool or confirmation-gated mutation path.

OpenAI-facing tools are read-only. Refund mutations are not model-selected write tools;
they run only after deterministic backend eligibility and an exact canonical customer
confirmation command.

Two valid execution modes share the same graph:

| Mode | Model involvement | Example |
| --- | --- | --- |
| Agent-assisted read/explanation | Model may classify language, select a narrowed read tool, and generate grounded wording. | Purchase history, policy, and eligibility questions. |
| Deterministic transaction | Backend recognizes the canonical command, validates persisted consent and workflow state, executes services, and authors the response. | Confirmed refund preparation or issuance. |

A backend operation is instrumented as a tool lifecycle even when the model did not
request it. “Tool call” therefore means an observable backend capability invocation;
“model call” means an actual provider request.

## Database Architecture

Implementation source:

* `apps/api/src/refunds_ai_api/database/migrator.py`
* `apps/api/src/refunds_ai_api/database/migrations/`
* `apps/api/src/refunds_ai_api/database/seeds.py`
* `apps/api/mockdata/identity_seed.json`
* `apps/api/mockdata/purchase_seed.json`

Schema layers:

| Layer | Tables |
| --- | --- |
| Migration metadata | `schema_migrations` |
| Identity | `users`, `roles`, `user_roles` |
| Catalog and history | `products`, `purchases` |
| Detail extensions | `digital_purchase_details`, `physical_purchase_details`, `subscription_purchase_details` |
| Model audit | `model_audit_sessions`, `model_audit_events`, `model_audit_event_lookup` |

PostgreSQL triggers derive refund deadlines and selected defaults:

* Digital: 15-day refund window, code delivery timestamp, redeemed-code lock reason.
* Physical: 30-day refund window.
* Subscription: 48-hour full-refund window, period-end refund window, cancellation defaults.

## Current Request Flows

### Customer Home

```text
/user-home?customerId=...
  -> getUserProfile()
  -> GET /api/users/{user_id}
  -> getUserPurchases()
  -> GET /api/users/{user_id}/purchases
```

### Purchase Detail

```text
/purchase-details/[purchaseId]
  -> GET /api/purchases/{purchase_id}/details
  -> GET /api/purchases/{purchase_id}/refund/eligibility
  -> type-specific detail components
```

### Refund Workflow Refresh

```text
chat refund side effect or physical carrier validation control
  -> Next.js same-origin proxy
  -> FastAPI refund or workflow endpoint
  -> ApplicationService
  -> refund policy evaluation
  -> guarded repository mutation
  -> route refresh
```

The help panel no longer exposes manual `Prep Refund` or `Issue Refund` buttons.
Chat owns refund initiation and issuance through confirmation-gated backend workflow
actions. Purchase detail pages visualize backend state and keep the physical carrier
acceptance control for local workflow validation.

### Chat

```text
help panel message
  -> Next.js /api/chat proxy
  -> FastAPI POST /api/chat
  -> AIChatService graph
  -> read-only tools or confirmation-gated backend workflow
  -> compact conversation_state returned to frontend
```

The chat request includes compact `page_context` and previous `conversation_state`.
It does not send full rendered page content or replay the full transcript.

### Model Audit Logging & Observability Stream

The audit foundation exists in `services/audit.py`, `repositories/audit.py`,
and migrations `014_create_model_audit_tables.py` and
`015_broadcast_model_audit_events.py`. `/api/chat` starts an audit session for
each valid chat request and carries the session through graph state.
`log_trace_step` persists each graph trace as an ordered audit event when a writer
is present. One audit session represents one user prompt and its resulting workflow,
not the full conversation. Follow-up prompts create new sessions; model-request events
separate the new user prompt from system instructions and prior-turn context injected
by the backend. PostgreSQL broadcasts inserted audit events through `pg_notify`.

Current persistence flow:

```text
Customer Message
  -> FastAPI /api/chat
  -> Create Model Audit Session
  -> Graph execution begins
  -> Node/Step execution:
       - Workflow Classify
       - Context Resolve
       - Tool Request / Completion
       - Mutation Start / Complete
  -> Persist Audit Event to Database
  -> Database broadcasts audit event notification
  -> /api/admin/audit/events/stream relays SSE event
  -> Route Response Returned
  -> Complete or Fail Model Audit Session
```

The admin home screen renders the first page of model-invocation cards from the
persisted audit read APIs, then lazy-loads older session pages as the user scrolls.
It subscribes to the audit SSE stream through a same-origin Next.js proxy and upserts
streamed session updates into the visible client-side list.
Session detail screens render one persisted audit session and subscribe to the same
SSE stream filtered by `session_id` so active session timelines refresh as new events
arrive.

The admin client preserves every persisted event and original sequence number. It maps
low-level trace types into audience-readable narrative titles, summaries, domain fact
labels, and labeled footer metadata without changing stored payloads.

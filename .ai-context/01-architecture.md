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
| `/technical-tour` | Client/Admin perspective cards with a shared product header and Exit link to `/`; Client selects a seeded mock customer and opens `/user-home`, Admin opens `/admin-home?tour=admin`. |
| `/user-home?customerId=...` | Demo builds always generate local history; integrated builds server-load profile/history outside `tour=client`. |
| `/admin-home` | Admin home screen with compact audit cards; demo mode or `tour=admin` renders generated examples, otherwise loads persisted audit records. |
| `/admin/sessions/[sessionId]` | Admin session detail screen with request identity, process/token metrics, tool outcomes, and ordered events; demo mode or `tour=admin` uses the generated example identified by the route. |
| `/purchase-details/[purchaseId]` | Demo mode and client tour render generated detail facts/policy summaries; integrated reads remain backend-owned. |

The root layout wraps every page in `ApplicationHelpLayer`. The help layer is only
available on `/user-home` and purchase detail routes.
Desktop chat reserves a responsive gap beside the page, with the tour background
continuing through that spacing and no visible divider. At viewport widths of
900px or less, chat occupies the full viewport with an X close control; background
content is inert and scrolling is locked until the panel closes. `ProductHeader`
uses its container width, capped at 1240px, with an intrinsic content minimum.
At 860px and above, the client identity header is a centered tab capped at 1240px;
its 1152px minimum adapts to available space with 12px side margins, keeping it
wider than the purchase body without crossing the reserved help-panel gap.
Below 860px, it spans the available page width, the brand uses its icon, and the
customer name stays centered in the same row as the swap and exit controls.
On the customer purchase-history screen, the help launcher is inline in that
header before swap and exit; tour purchase details use the same inline launcher.
Technical-tour headers, perspective cards, customer summary cards, and purchase
cards use light warm glass surfaces with brown text. Purchase category labels and
subtle right-edge gradients distinguish digital, physical, and subscription types.
The public landing header retains its dark treatment. Tour purchase details reuse
the client header and inline help control, with a back link preserving tour context.
`demo-purchase-detail.ts` mirrors seed events, not backend eligibility decisions.
The help composer starts at one line and uses CSS content sizing to grow upward
as text wraps, capped at 180px or 30% of the viewport height before scrolling.
Text reserves space for the send button, anchored inside the bottom-right corner.

The product landing branch is presentational. It does not load backend data or expose
chat and refund controls. The root route opts out of static prerendering so selection
uses the shared build/development mode flag from `demo-mode.ts`; the public landing
is the default when the variable is absent.

Frontend-only Docker development uses `docker-compose.dev.yml` and the `development`
target in `apps/web/Dockerfile`. That topology runs only the Next.js development server,
bind-mounts `apps/web`, keeps `.next` in a container volume, and uses webpack polling
for reliable Windows bind-mount updates. The standard `docker-compose.yml` remains the
production-style integrated web/API topology.

The customer home screen renders purchase cards from backend data. Before navigating,
each card stores a small session-storage header summary for purchase detail continuity.
The detail route still loads authoritative detail data from FastAPI.
For `tour=client`, `apps/web/src/lib/demo-purchases.ts` instead builds display-only
history from frontend-owned identity and purchase seed snapshots in `src/lib/fixtures`. It mirrors the
backend's seed ordering, IDs, product selection, statuses, and date offsets with the
current UTC day anchored at 14:00. The server rebuilds the snapshot for every load;
there are no API reads or persisted purchase objects. The entry selects Avery Brooks
consistently. Tour cards are labeled `Simulated Purchase History` and link to presentation-only purchase details preserving customer and tour context. The help trigger opens a fixed local preview with no live service connection.
Integrated pages retain their backend data and mutation paths.
The customer home uses `ProductHeader` and `tour-shell.module.css` to share the tour
entrance banner and light gradient. The customer name is centered in the banner;
the body begins with summary metrics and purchase history without a separate welcome
card. Its icon-only Exit link clears the mock customer selection and returns to `/`.
A dual-arrow button opens a native confirmation dialog before navigating to the admin
entry: Continue stays on the client tour, Swap opens `/admin-home?tour=admin`. The dialog warns
that tour progress is not saved and the admin tour starts from the beginning. It does
not reset persisted purchases, refunds, or audit records. Admin tour pages reuse the warm glass layout and signed-in banner; swapping from admin restarts the fixed client tour.

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


### Admin tour presentation

`apps/web/src/lib/demo-audit.ts` rebuilds six terminal illustrative audit sessions
with stable IDs and dates relative to the current UTC day. Explicit `tour=admin`
list/detail routes skip backend reads and live subscriptions. Unknown example IDs
return not found. Cards preserve tour context; direct detail reloads rebuild the
same examples. `AdminAuditSessionList` disables repair reads, pagination, and SSE
in tour mode, while `AdminSessionDetailPage` omits live refresh. All examples are
presentation-only and model/provider metrics remain separate from backend estimates.

Admin tour summaries aggregate the complete generated set with
`audit-summary.ts`: session count, shared success/failure card, provider token total,
and per-session averages for events, tools, latency, and time to response. Timing
averages exclude unavailable values. Admin cards use restrained warm neutral surfaces
and light borders, retaining the shared tour header and background.

Admin tour session detail review leads with a six-metric session snapshot, the
conversation, tool purposes/outcomes, and every event in its original sequence.
`AdminSessionDetailPage` keeps full session metadata, tool fields, event context,
and raw payloads in expandable inspection sections (open initially for live routes).
Timestamped events show elapsed time from session start where parsing is possible;
original timestamps remain available for inspection. No stored evidence is discarded.

### Frontend-only deployment boundary

`demo-mode.ts` defaults to demo and uses the mode fixed by `next.config.ts` at build
or development startup. Server and client guards share the same public flag. Query
parameters and production runtime environment changes cannot unlock a demo build.
All customer/admin page routes select local fixtures before any API reads; unknown
IDs do not fall back to FastAPI. All nine service proxies reject demo requests with
404/DEMO_SERVICE_DISABLED before consuming input or making requests. The API data
layer, chat submission, audit subscriptions, and live purchase calls also guard
against accidental use. Demo help is a fixed local preview with a disabled composer.
The demo CSP allows connections/assets only to the same origin. Local Next navigation
remains available. Integrated code requires an explicit non-demo build.

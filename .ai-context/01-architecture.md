# 01-architecture.md

# System Architecture

## Overview

The platform follows a layered architecture that separates presentation, backend services, AI orchestration, business logic, and persistent storage into independent layers.

Each layer has a single responsibility and communicates only through well-defined interfaces.

```text
Customer / Administrator
           │
           ▼
    Next.js Frontend
           │
           ▼
     FastAPI Backend
           │
           ▼
    OpenAI Model Layer
           │
           ▼
     Backend Tool Layer
           │
           ▼
 Deterministic Business Services
           │
           ▼
  Supabase PostgreSQL
```

---

## Frontend

**Technology**

* Next.js
* TypeScript
* Tailwind CSS

**Primary Interfaces**

* Customer Portal
* Admin Operations Dashboard
* Persistent Chat Interface
* Voice Interface

**Current Frontend Routes**

* `/` renders the mock authentication landing page.
* `/user-home` renders the customer home screen from a `customerId` query parameter.
* `/admin-home` renders the administrator home placeholder.
* `/purchase-details/[purchaseId]` renders a server-loaded purchase detail page from `GET /api/purchases/{purchase_id}/details`.

The mock landing page derives local-only credentials from seeded identities, animates those credentials into read-only form fields, and then navigates to the appropriate home route. Customer home rendering uses the route query parameter rather than browser-only state so server-rendered and hydrated output match on refresh.

Purchase detail rendering uses one stable route and one stable backend detail endpoint. The frontend passes purchase summary data from the purchase history card for header continuity, then loads the authoritative purchase detail payload from the API. The detail page renders product-type-specific sections:

* Digital purchases show purchase/code issuance steps and issued-code redemption state under `Code Details`. Once the code is invalidated during refund preparation, the code section remains visible but muted and a `Return Details` section displays the invalidated-code state and invalidation timestamp. Digital metadata is not duplicated in a generic metadata section.
* Physical purchases show delivery steps and delivery tracking data. Once a physical return is requested, the delivery and tracking context remains visible but muted, and a return workflow row becomes the active context with return-requested, label-created, and courier-acceptance fields.
* Subscription purchases show billing-cycle progress under `Billing Cycle Details`. Prepared or issued subscription refunds add `Return Details` rows beneath the billing cycle instead of using a header badge.

Prepared subscription refund state is visualized in the subscription billing-cycle section and a dedicated return summary. When `service_ended_at` is present, the cycle marker changes from `Today` to `Cancelled`, displays the service-ended date, and renders the remaining cycle track in red. Once backend refund workflow state reports the subscription is prepared, the return summary shows auto-renewal off, days used in the billing cycle, and `Subscription Cancelled`. Once the refund is issued, a second return row shows cancel date, refund amount, and the expected 3-10 business day refund window. Subscription metadata should avoid duplicating this lifecycle display; cancellation, service end, proration, and refund window deadline fields are not shown as standalone metadata cards.

The customer purchase summary page and purchase detail pages expose a fixed bottom-right help trigger. The root application shell owns the persistent help layer so the panel state can survive navigation between those purchase surfaces. Opening the trigger shifts the main application content left, slides in a full-height right-side help panel, and moves the trigger with the content edge. The trigger shows a chat icon when closed and a collapse-panel icon when open.

The help panel now includes one consistent chat surface across the customer purchase summary page and purchase detail pages. The shared surface renders a transcript area, a bottom text composer, a disabled microphone affordance for future voice support, and a send control. Submitted chat messages are forwarded through the same-origin frontend chat proxy to the FastAPI `POST /api/chat` endpoint. The endpoint validates non-empty text, runs a LangGraph workflow, lets the configured OpenAI model request read-only tools, and returns a model-generated plain-text assistant response without Markdown formatting. Supported tools include purchase-history retrieval, deterministic amount-threshold purchase counts, deterministic date-range purchase history, and deterministic refund policy lookup. The chat request includes compact page context, either the purchase-history surface or a purchase-detail surface plus purchase id. The chat response also returns compact conversation state, including selected purchase type, product, purchase id, selected purchase ids, policy scope, date range, and a backend-resolved current-page reference. The frontend sends that state on the next message so follow-up policy questions can resolve references like "those purchases" or "that one" without replaying the full transcript. Scoped follow-ups using "one", "that one", "those", "most recent one", or "latest one" resolve inside the selected purchase id set first; the graph only falls back to the global most recent purchase when no selected set exists. If the model requests no supported tool, the backend executes the narrowest deterministic read-only tool for supported account or policy intent and skips account tools for off-topic customer messages. If the model requests broad purchase history for a resolvable date-bounded or policy question, the backend overrides that selection with the narrower tool before querying account data. Explicit product-name follow-ups escape any narrowed selected set, resolve through exact, normalized, partial, fuzzy, SKU, or order-number matching against the active customer's full backend purchase rows, then use the resolved purchase type for policy lookup. Named product references must resolve to an actual purchase before product-specific policy lookup; unresolved products return a clarification and do not fall back to inferred product-type or global policy answers. Purchase-detail page follow-ups may resolve "this item" from the current page purchase id into only purchase id, product name, sku, order number, and purchase type; full rendered page content is not sent to the model. Factual account responses are blocked unless authoritative tool data exists. Policy explanations are allowed only from backend policy catalog tool results and must stay scoped to the customer request. The graph is limited to account, purchase-history, order, account-activity, refund-policy, and refund-flow topics. It must not assess refund eligibility, capture voice input, persist conversation logs, or mutate business state.

The help panel is a command surface, not the refund state display. On purchase detail routes it reads backend refund workflow eligibility and renders `Prep Refund` and `Issue Refund` commands. Those commands are disabled by default and become enabled only when FastAPI reports `can_prepare_refund` or `can_issue_funds`. `Prep Refund` calls the same-origin frontend proxy route for `POST /api/purchases/{purchase_id}/refund/request`; `Issue Refund` calls `POST /api/purchases/{purchase_id}/refund/issue`. After successful mutations, the help layer refreshes the current route and lets the purchase detail page visualize updated lifecycle state. Backend services remain responsible for deciding whether refund actions are allowed.

Physical returns also include a detail-page `Given to Carrier` control in the active return workflow row. It calls the carrier-acceptance endpoint, refreshes refund eligibility, and enables fund issuance only after the backend confirms the state change.

The manual help-panel refund commands are temporary frontend controls used to validate layout, backend workflow wiring, and pending/issued-state presentation before AI orchestration is active. Once the agent workflow can invoke refund tools directly, these explicit manual buttons should be removed or demoted so the agent owns refund initiation and issuance while the detail page continues to own state visualization.

Phase 1 AI Agent Integration establishes dependencies, configuration, the shared chat UI, same-origin chat proxying, a FastAPI chat endpoint, LangGraph orchestration, OpenAI model calls, backend-owned read-only purchase intelligence tools, deterministic account-fact guards, and sequential console-visible trace log emission. Phase 2 adds deterministic read-only refund policy lookup from the backend policy catalog. Account-specific refund eligibility evaluation, voice capture, persisted AI logs, and refund workflow mutation through the agent remain future phases.

---

## Backend

**Technology**

* FastAPI
* Python

**Primary Responsibilities**

* API endpoints
* Session management
* AI request orchestration
* Tool execution
* Business service coordination
* Audit logging

---

## Database

**Technology**

* Supabase PostgreSQL

**Primary Data**

* Customers
* Purchases
* Purchase detail records with refund lifecycle state
* Policies
* Support Sessions
* AI Events
* Voice Transcripts

Refund state is not stored in a standalone `refunds` table. Refund eligibility is computed from persisted purchase and purchase-detail state. Each purchase type owns the fields required by its own refund policy:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

The backend policy layer reads those records, evaluates the product-specific policy, and persists approved lifecycle changes back to the owning detail table.

---

## Model Layer

**Technology**

* OpenAI APIs
* Function Calling
* Voice Transcription

**Purpose**

* Intent recognition
* Context gathering
* Response generation
* Backend tool orchestration
* Customer and administrator communication

---

## Tool Layer

The model interacts with backend functionality exclusively through structured tools.

Tool categories include:

* Customer
* Purchases
* Refund workflows backed by purchase detail state
* Policies
* Support History
* Administration
* Audit

---

## Voice Flow

Voice interactions follow the same architecture as text conversations.

```text
Voice Input
      │
      ▼
Speech Transcription
      │
      ▼
Model Orchestration
      │
      ▼
Backend Tools
      │
      ▼
Business Services
      │
      ▼
Response
```

---

## High-Level Request Flow

Every interaction follows the same system path.

```text
User
→ Frontend
→ Backend
→ Model
→ Tool Calls
→ Business Services
→ Database
→ Business Services
→ Model Response
→ Frontend
```

The architecture intentionally separates user interaction, AI orchestration, business operations, and persistent data into independent layers to maintain modularity, auditability, and clear system ownership.

## Refund Evaluation Flow

Refund requests follow a database-backed deterministic path:

```text
User requests refund
        |
        v
Backend loads purchase
        |
        v
Backend loads matching purchase detail record
        |
        v
Backend verifies refund window
        |
        v
Backend evaluates product-specific policy
        |
        v
Backend executes refund strategy
        |
        v
Backend persists updated detail-table refund state
```

The AI agent may explain outcomes and orchestrate tools, but it does not infer refund eligibility independently.

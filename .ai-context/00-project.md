# 00-project.md

# Project Overview

## Vision

RefundsAI is a production-inspired agentic customer support platform that can guide
and execute refund workflows against strict backend-owned policy.

The AI assistant is the conversational interface. It can understand customer intent,
gather context, call backend tools, explain outcomes, and guide approved workflows.
It is not the business authority.

Backend services, deterministic policy code, and persisted database facts decide
refund eligibility and refund lifecycle transitions.

The finished project demonstrates a bounded agent rather than an autonomous financial
authority. Model calls are used where language interpretation, read-tool selection,
or customer-facing explanation adds value. Exact confirmation turns may bypass the
model entirely: deterministic code validates consent, executes the guarded workflow,
verifies persistence, and returns a backend-authored transactional response.

## Current Implementation

Implemented surfaces:

* Next.js customer portal in `apps/web`.
* Environment-gated public product landing page at `/` for demo presentation.
* FastAPI backend in `apps/api`.
* Supabase PostgreSQL migrations and seed data.
* Mock customer and administrator entry paths.
* Customer purchase history and purchase detail screens.
* Type-specific purchase detail presentation for digital, physical, and subscription purchases.
* Backend refund workflow evaluation, preparation, issuance, digital code redemption, and physical carrier acceptance.
* LangGraph-backed chat endpoint for purchase facts, refund policy, refund eligibility, and confirmation-gated refund actions.
* Persisted model audit sessions and ordered audit events for chat execution.
* Admin audit session list, session detail timeline, token/latency summaries, and realtime SSE-backed refresh.

Current project state:

* The core technical challenge is complete through text chat, strict policy evaluation,
  confirmation-gated refund execution, and administrative auditability.
* The repository is in final project/submission state. Remaining work should be
  presentation preparation, selective polish, validation hardening, or explicitly
  deferred production scope.

Not yet productionized:

* Real authentication and authorization.
* Real payment processing.
* Production-grade support case management.
* Voice capture, transcription, and voice responses.
* Production deployment hardening.

## Core Product Rule

Refund state belongs to the purchase type that owns the operational lifecycle:

* Digital refund state: `digital_purchase_details`
* Physical refund state: `physical_purchase_details`
* Subscription refund state: `subscription_purchase_details`

The shared `purchases` table stores purchase history plus workflow summary facts such
as `status`, `refund_requested_at`, `refunded_at`, `refund_amount_cents`, and
`refund_outcome`.

No standalone `refunds` table should be introduced under the current architecture.

## Primary Interfaces

### Product Landing

The root route presents RefundsAI as a commercially integrable, policy-governed support
product. It is a static conceptual surface and does not call the API, database, or model.
`REFUNDS_AI_DEMO_MODE=false` restores the mock authentication screen at `/` for
integrated application walkthroughs.

### Customer Portal

Customers can:

* Enter through mock login.
* View account summary metrics.
* Browse seeded purchase history.
* Open one stable purchase detail route: `/purchase-details/[purchaseId]`.
* Ask the shared help panel about purchases, policy, eligibility, and refund process actions.
* Confirm eligible refund process actions through the chat workflow.

### Admin Dashboard

The Admin Dashboard is designed to serve as an **AI Auditability and Observability Suite**, rather than a customer account management panel. 

The primary goal is live monitoring and historical review of the complete agent
workflow, including model calls and deterministic backend operations:
* **Audit Session Overview**: Displays a reverse-chronological timeline of customer-agent chat sessions.
* **Audit Session Details**: Request identity, process metrics, actual and estimated
  token metrics, tool purposes and outcomes, and a narrative rendering of every
  persisted execution event.
* **Realtime Event Streaming**: SSE relays database-broadcast audit notifications so
  active session lists and timelines refresh from persisted state.

Actual model token totals remain separate from deterministic tool estimates. A
successful confirmation-only refund session may correctly report zero model calls and
zero provider tokens.

## Technology Stack

Frontend:

* Next.js
* TypeScript
* React
* CSS modules and global CSS
* Framer Motion for motion where used

Backend:

* FastAPI
* Python
* Pydantic response schemas
* psycopg for PostgreSQL access

Database:

* Supabase PostgreSQL
* Ordered Python migration modules
* Idempotent seed steps

AI:

* OpenAI chat completions client
* LangGraph workflow
* Backend-owned tool execution

## Repository Philosophy

This repository is documentation-first.

`.ai-context/` is the authoritative project context. Source code, migrations, tests,
and package scripts remain the implementation source of truth. When documentation and
implementation drift, inspect the code and update the docs rather than preserving stale
or generic guidance.

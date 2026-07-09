# 02-boundaries.md

# Responsibility Boundaries

## Authority Model

RefundsAI uses AI for conversation and orchestration, not business authority.

```text
Database facts
  -> deterministic policy helpers
  -> application services
  -> FastAPI contracts
  -> AI assistant and frontend presentation
```

The frontend and language model receive evaluated facts. They do not create the facts
that decide eligibility, amounts, state transitions, or refund deadlines.

## Implementation Boundary Map

Frontend:

* Owns presentation, local mock-login hints, same-origin proxying, and chat panel state.
* Must not own customer authority, refund eligibility, policy decisions, financial state, or database access.

FastAPI routes:

* Own request/response contracts, status-code mapping, and dependency construction.
* Must not own business policy or SQL implementation details.

Application services:

* Own business workflow coordination and policy enforcement.
* Must not own frontend presentation or model reasoning.

Repositories:

* Own SQL reads, SQL writes, and transaction guards.
* Must not own policy decisions or customer-facing text.

Policy helpers:

* Own deterministic refund workflow decisions.
* Must not own persistence, HTTP response formatting, or model prompt behavior.

AI chat graph:

* Owns intent classification, context resolution, tool orchestration, and response grounding.
* Must not own eligibility authority, direct database access, or ungated writes.
* May terminate in a backend-authored response when a deterministic transactional path
  does not require another model call.

Database:

* Owns persistent business facts, constraints, and trigger-derived fields.
* Must not own customer-facing explanations or model prompts.

## Customer Boundary

Customers may:

* View their selected mock account.
* View their own purchase history.
* View backend-evaluated refund workflow state.
* Ask the assistant about account facts, policies, and eligibility.
* Confirm eligible refund process actions through exact canonical commands.

Customers may not:

* Access another customer's data.
* Override backend policy decisions.
* Submit authoritative refund state, refund amount, or deadline fields.
* Bypass preparation and directly issue funds.

Current authentication is mocked. The selected customer id is carried through
`/user-home?customerId=...` and browser session storage for local UI continuity only.

## Administrator Boundary

Administrators may enter the mock admin surface and inspect model audit sessions,
ordered execution events, token/latency metrics, workflow/tool/mutation indicators,
and realtime audit updates for chat interactions.

The admin surface distinguishes provider model usage from deterministic backend work.
Actual tokens and model calls describe provider activity; estimated tool input/output
tokens describe serialized backend payload size and are not billed model usage.

Production admin behavior should require customer verification before broader
customer-specific support data is shown. Admin workflows remain subject to backend
policy and audit boundaries.

The current admin dashboard is an AI auditability surface, not a mature customer
operations or case-management console.

## Frontend Boundary

The frontend can:

* Render backend API data.
* Store small non-authoritative UI hints, such as selected mock customer and purchase detail header summary.
* Send compact chat `page_context` and previous `conversation_state`.
* Proxy browser calls to FastAPI through same-origin route handlers.

The frontend cannot:

* Read Supabase directly.
* Decide refund eligibility.
* Construct refund lifecycle state.
* Treat session storage as authentication.
* Transform backend refund decisions beyond display mapping.

## Backend Boundary

The backend is the authoritative application layer.

It owns:

* Database connectivity through `SUPABASE_DB_URL`.
* API response envelopes.
* Repository access.
* Policy enforcement.
* AI tool execution.
* Refund workflow mutations.
* Conflict handling for stale or duplicate writes.

Known backend source files:

* Routes: `apps/api/src/refunds_ai_api/routes/`
* Services: `apps/api/src/refunds_ai_api/services/`
* Repositories: `apps/api/src/refunds_ai_api/repositories/`
* Migrations: `apps/api/src/refunds_ai_api/database/migrations/`

## Language Model Boundary

The language model may:

* Interpret user intent.
* Ask for read-only tools.
* Explain backend-provided purchase, policy, and eligibility facts.
* Produce customer-facing confirmation prompts.

The language model may not:

* Infer refund eligibility from partial context.
* Override deterministic policy.
* Choose or widen `customer_id`.
* Access the database directly.
* Prepare or issue refunds through an OpenAI-facing write tool.
* Claim a mutation completed unless backend execution confirms it.

The language model is not required for every chat turn. Canonical refund confirmation,
validated mutation execution, persistence verification, and transactional success
wording can be completed deterministically.

## Refund Authority

Refund workflow state belongs to existing purchase tables:

* `purchases` stores shared purchase state and issued refund facts.
* `digital_purchase_details` stores digital entitlement and invalidation state.
* `physical_purchase_details` stores delivery, return label, carrier, and return state.
* `subscription_purchase_details` stores period, cancellation, renewal, and proration state.

The current architecture intentionally excludes a standalone `refunds` table.

## Escalation Boundary

The assistant should escalate or defer when:

* Policy requires human review.
* The customer asks for a human representative.
* Identity, ownership, or product reference is unclear.
* A product reference is ambiguous.
* A requested workflow action is blocked by policy.
* The request is outside account, purchase, order, account activity, policy, or refund topics.

Escalation and production support case history are deferred production-scope work.

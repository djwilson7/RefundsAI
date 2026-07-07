# 12-security.md

# Security Boundaries

## Purpose

This document defines current trust boundaries, intentionally mocked security behavior,
and production security considerations.

## Security Principles

* Backend services are the application security boundary.
* The frontend is not trusted as a source of truth.
* API keys and database credentials stay server-side.
* Business policy is enforced server-side.
* Refund lifecycle state is database-backed and backend-controlled.
* AI-generated reasoning is never authoritative for eligibility, amounts, deadlines, or workflow transitions.

## Mocked Security

The following are intentionally mocked:

* Customer authentication.
* Administrator authentication.
* Customer identity verification.
* Financial transactions.
* Payment processing.

Mock auth exists to demonstrate user flow. It does not provide production identity,
authorization, or session guarantees.

## Production Security Not Yet Implemented

Production scope would require:

* Secure authentication.
* Session management.
* Role-based authorization.
* Customer identity verification.
* Rate limiting.
* Durable audit logging.
* Secure payment processing.
* Secrets rotation and deployment hardening.

These remain outside the current technical-demo scope.

## Environment Variables

Backend-only environment variables:

* `SUPABASE_DB_URL`
* `DATABASE_CONNECT_TIMEOUT_SECONDS`
* `OPENAI_API_KEY`
* `OPENAI_MODEL`

Frontend server-side configuration:

* `REFUNDS_AI_API_BASE_URL`

Rules:

* Do not commit secrets or local `.env` values.
* Do not expose `SUPABASE_DB_URL` or `OPENAI_API_KEY` to browser code.
* Browser requests should use frontend route handlers or backend APIs, never direct service credentials.

## Frontend Trust Boundary

The frontend may store local UI hints:

* selected mock customer id
* purchase detail header summary
* current chat transcript and compact conversation state

These are not authoritative.

Frontend state must not be trusted for:

* customer identity
* authorization
* purchase ownership
* refund eligibility
* refund lifecycle state
* refund amount or outcome
* refund deadlines
* financial state
* administrative permissions

## Backend Trust Boundary

FastAPI routes and backend services own:

* database access
* OpenAI access
* policy enforcement
* workflow transitions
* API response contracts
* error/status mapping

Routes should not trust client-submitted refund state. They should call services, and
services should load current database facts before making decisions.

## Database Security

The backend is the only application layer allowed to connect to Supabase PostgreSQL.

Business tables enable row-level security in migrations. Initial policies grant access
to Supabase `service_role`, preserving backend-only database access while production auth
is out of scope.

Tables with backend-only RLS policies:

* `users`
* `roles`
* `user_roles`
* `products`
* `purchases`
* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`
* `model_audit_sessions`
* `model_audit_events`
* `model_audit_event_lookup`

`schema_migrations` is migration metadata and not business data.

## Refund Security Boundary

Refund lifecycle state is split across:

* `purchases`
* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

No client or AI tool may provide authoritative values for:

* `refund_window_expires_at`
* `full_refund_window_expires_at`
* `refund_requested_at`
* `refunded_at`
* `refund_amount_cents`
* `refund_outcome`
* `code_invalidated_at`
* `return_label_created_at`
* `accepted_by_carrier_at`
* `cancelled_at`
* `service_ended_at`
* `refund_proration_mode`

PostgreSQL triggers derive deadline/default fields. Backend services execute guarded
mutations for workflow commands. Duplicate, stale, or invalid commands should return
workflow conflicts rather than silently rewriting timestamps or returning pretend success.

## AI Security Boundary

The model may access backend tools only through the chat graph.

Current OpenAI-facing tools are read-only:

* purchase history
* date-range purchase history
* amount-threshold counts
* refund policy
* refund eligibility

The model must not:

* access the database directly
* choose or widen customer identity
* infer eligibility without backend tool data
* mutate refund state through tool arguments
* claim a refund was prepared or issued unless backend execution confirms it

Refund process mutations require deterministic backend context, a backend-validated
canonical confirmation command, persisted confirmation authorization, and current
workflow permission.

The model is not the authority for refund consent. The backend confirmation validator
must persist exact consent facts before any refund mutation can execute. Mutation
execution must reload those facts and verify that confirmation is granted, matched,
scoped to the active customer and purchase, tied to the current expected command,
unused, and allowed by the current workflow stage.

Generic confirmations such as `yes`, `proceed`, `do it`, and `continue` are not valid
write approval at the canonical-command boundary.

## Response Safety

Customer-facing assistant responses should avoid internal implementation terms such as:

* graph
* node
* resolver
* tool
* selected set
* state
* mutation
* persisted state
* `issue_funds`
* `invalidate_code`
* `cancel_subscription`
* `required_action`

The assistant should redirect off-domain questions back to account, purchase, order,
account activity, policy, or refund process topics.

## Repository Security

Repository contributors must:

* Keep secrets out of source control.
* Keep local environment files untracked.
* Validate security-sensitive changes before merge.
* Update `.ai-context/12-security.md` when trust boundaries change.
* Update tests when security behavior is enforced by code.

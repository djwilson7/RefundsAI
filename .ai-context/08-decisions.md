# 08-decisions.md

# Architectural Decisions

## Purpose

This file records durable decisions that should shape future implementation.

Use it when a choice establishes long-term architecture, ownership, or tradeoffs.
Routine implementation notes belong in the relevant context document instead.

## Decision Format

Each decision should answer:

* What was decided?
* Why was it decided?
* What does it constrain or enable?

## Decisions

### Decision 001: Mock Authentication

Decision: Customer and administrator authentication remain mocked.

Reason: The project is focused on AI product behavior, refund policy, and deterministic
workflow architecture, not identity infrastructure.

Consequence: Do not add production authentication unless project scope changes. Mock
login state is a local UI aid and must not become backend authority.

### Decision 002: Deterministic Policy Enforcement

Decision: Refund eligibility and workflow transitions are enforced by backend services,
not by the language model.

Reason: Refund decisions must be deterministic, auditable, and consistently testable.

Consequence: AI may explain backend outcomes and orchestrate tools, but it cannot
override policy or infer eligibility.

### Decision 003: Desktop-First Experience

Decision: Desktop web is the primary target.

Reason: The project prioritizes AI workflow behavior over cross-platform polish.

Consequence: Mobile optimization is secondary unless scope changes.

### Decision 004: Documentation-First Development

Decision: `.ai-context/` is the authoritative project context.

Reason: Human contributors and AI agents need centralized architecture, business, and
contract guidance.

Consequence: Behavior changes should update the relevant context docs alongside code.

### Decision 005: Normalized Identity Layer

Decision: Human identity is modeled with `users`, `roles`, and `user_roles`.

Reason: This separates identity basics from role assignment while keeping mocked
authentication lightweight.

Consequence: Domain entities should reference `users.id`. Role-specific behavior should
come through `user_roles`, not duplicated columns on `users`.

### Decision 006: Consolidated Mock Product Catalog

Decision: Physical, digital, and subscription offerings share one `products` table.

Reason: A small technical demo needs representative purchase data without production
catalog complexity.

Consequence: Use `products.product_type` and `purchases.purchase_type` for product-type
behavior. Split catalog tables only if future scope requires production catalog features.

### Decision 007: Purchase Detail Extension Tables

Decision: Type-specific mutable purchase fields live in one-to-one detail tables:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

Reason: Digital, physical, and subscription purchases have different lifecycle facts.
Keeping them on `purchases` would create a nullable multi-purpose table.

Consequence: Load `purchases` first, then exactly one matching detail row based on
`purchases.purchase_type`. Cross-table exclusivity is validated by seed tests and
backend service logic rather than cross-table triggers.

### Decision 008: Refund State Lives With Purchase Details

Decision: Refund lifecycle state is embedded in purchase detail tables instead of a
standalone `refunds` table.

Reason: Refund policy depends on product-specific lifecycle facts: code redemption,
return carrier acceptance, subscription period/cancellation, and related state.

Consequence: Do not introduce a standalone `refunds` table under the current architecture.
Backend services compute eligibility from `purchases` plus the matching detail row.

### Decision 009: Chat Uses Deterministic Workflow Routing

Decision: AI chat uses deterministic object-operation workflow routing around a small
LangGraph shape.

Reason: The model can help interpret language, but backend code must choose the
authoritative purchase scope, policy scope, eligibility target, and mutation gate.

Consequence: Keep OpenAI-facing tools read-only. Route account facts, policy, eligibility,
and refund process actions through `services/ai_chat/workflows/`. Refund mutations require
backend eligibility plus the exact canonical confirmation command.

### Decision 010: Core Scope Stops At Text Agent And Auditability

Decision: The core technical challenge scope is complete through text-based AI chat,
confirmation-gated refund workflow execution, and administrative model auditability.

Reason: These surfaces prove the central product claim: the model can converse and
orchestrate while backend policy, persisted facts, and audit records remain authoritative.

Consequence: Voice-agent support, production authentication, payment integration,
hosted deployment, mobile polish, and production support case management are deferred
unless intentionally promoted. Future work should focus on polish, model quality,
user experience tuning, validation hardening, or explicit deferred items.

### Decision 011: Transactional Confirmation Turns May Skip The Model

Decision: Exact refund-confirmation turns may execute and respond through deterministic
backend code without an OpenAI request.

Reason: Once the backend has resolved the purchase, supplied the canonical command,
persisted exact consent, and verified current workflow permission, another model call
adds cost and uncertainty without adding authority.

Consequence: Model calls and backend tool calls are independent audit metrics.
Confirmation-only sessions may report zero provider tokens. Transactional wording must
come from verified backend results and safe response templates.

### Decision 012: Audit Storage Remains Raw; Presentation Becomes Narrative

Decision: Persist every ordered audit event and raw payload, then translate those facts
into readable titles, summaries, labels, and tool descriptions in the admin client.

Reason: Technical evidence should remain complete while the review experience must be
understandable to product, engineering, and operational audiences.

Consequence: Do not collapse, filter, or renumber stored events in the session timeline.
Presentation mappings may clarify event types and domain facts but must retain original
sequence and expandable payloads.

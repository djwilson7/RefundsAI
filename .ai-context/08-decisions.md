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
`purchases.purchase_type`. For v1.0, cross-table exclusivity is validated by seed tests
and backend service logic rather than cross-table triggers.

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

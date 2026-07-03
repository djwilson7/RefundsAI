# Developer Insights

## Purpose

This document captures engineering reasoning, implementation tradeoffs, and system-design thinking throughout the project.

It is not the authoritative source for project rules. Those live in `.ai-context/`.

This file explains why the project evolves the way it does.

---

## Insight 001 — Context Before Code

Before scaffolding the application, the project establishes a context layer that defines vision, architecture, business boundaries, testing expectations, API contracts, database ownership, tool specifications, and security boundaries.

Reason:

This project is a presentation-grade technical challenge, not a disposable prototype. Establishing context first allows faster implementation later while reducing architectural drift, unnecessary rewrites, and model-generated scope creep.

Tradeoff:

This delays initial coding, but improves implementation velocity once development begins.

---

## Insight 002 — Agent Behavior First

The primary evaluation target is the agent workflow.

The project prioritizes:

- policy-governed refund decisions
- tool orchestration
- edge-case denial behavior
- auditability
- trace visibility

Reason:

The Loom evaluation specifically asks for a live agent demo, code tour, and reasoning logs. The user interface supports the agent workflow, but the agent workflow is the core product proof.

---

## Insight 003 — Local-First Development

The project is scoped for local development rather than immediate deployment.

Reason:

The technical challenge requires a GitHub repository, README, and Loom walkthrough. Local reproducibility is more important than deployment infrastructure during the early milestones.

Tradeoff:

A hosted demo may be added later, but deployment should not block core agent functionality.

---

## Insight 004 - Refund State Belongs With Purchase Details

Refund state is embedded into the product-type-specific purchase detail tables instead of a standalone `refunds` table.

Reason:

Digital, physical, and subscription purchases have materially different refund-blocking facts. A redeemed digital code, a physical carrier acceptance event, and a subscription billing-period proration are not the same kind of state. Keeping those facts with the purchase detail table that owns the product lifecycle avoids duplicated state, keeps ownership clear, simplifies policy evaluation, makes SQL authoritative, reduces synchronization problems, and lets backend services and AI tools consume identical data.

Tradeoff:

Policy queries need to join `purchases` to the matching detail table before evaluation. That is acceptable because the purchase type already determines which detail table is authoritative, and it avoids a generic refund table that would either duplicate state or become a sparse catch-all model.

The database should also compute derivable refund deadlines. Letting PostgreSQL triggers derive refund windows from `purchases.purchased_at` reduces network payloads, prevents clients from spoofing deadline values, and keeps future backend services focused on sending event facts instead of recalculating database-owned state.

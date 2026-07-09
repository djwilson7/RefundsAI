# 07-documentation.md

# Documentation Standards

## Purpose

Documentation is part of implementation. It should help contributors understand the
current system without forcing them to infer architecture, contracts, or business rules
from code alone.

## Source of Truth

Use this precedence when docs and code appear to conflict:

1. Source code, migrations, seed files, tests, package scripts, and schemas.
2. `.ai-context/` documentation.
3. README and other general project prose.

If `.ai-context/` is stale, update it as part of the change.

## Documentation Style

Prefer:

* Short sections with one purpose.
* Tables for contracts, ownership, and endpoint lists.
* Concrete file references.
* Explicit implementation boundaries.
* Examples only when they clarify a real contract.

Avoid:

* Dense paragraphs that combine multiple concepts.
* Repeating the same rule across many documents without adding local context.
* Documenting aspirational surfaces as mature implementation.
* Copying large code or payload blocks when a field table is clearer.

## What To Document

Update `.ai-context/` when changes affect:

* Architecture or ownership boundaries.
* API routes, request fields, response fields, or error codes.
* Database tables, constraints, triggers, seeds, or migration flow.
* Refund policy, workflow stages, required actions, or mutation guards.
* AI tool schemas, workflow routing, model-context state, or response guards.
* Security boundaries or trust assumptions.
* Testing expectations.

## File Responsibilities

| File | Responsibility |
| --- | --- |
| `00-project.md` | Product scope and current implementation state. |
| `01-architecture.md` | Layer map and request/workflow flow. |
| `02-boundaries.md` | Authority and responsibility boundaries. |
| `03-business-logic.md` | Deterministic policy and workflow rules. |
| `04-personas.md` | Actors and permissions. |
| `05-standards.md` | Engineering conventions. |
| `06-testing.md` | Validation expectations and test surfaces. |
| `07-documentation.md` | Documentation rules. |
| `08-decisions.md` | Durable architectural decisions. |
| `09-api.md` | Frontend/backend HTTP contracts. |
| `10-database.md` | Schema, migrations, seeds, and data ownership. |
| `11-tools.md` | AI tool and chat orchestration contracts. |
| `12-security.md` | Trust, secrets, RLS, and safety boundaries. |

## Inline Comments

Use inline code comments for non-obvious implementation choices:

* Business rule edge cases.
* SQL guard behavior.
* AI routing or response guard logic.
* Date, money, or timezone conversions.

Do not comment obvious syntax or restate function names.

## Review Checklist

For documentation changes:

* Does the doc name the implementation source file when behavior is code-backed?
* Are broad claims tied to implemented routes, services, migrations, or tests?
* Are future-phase features clearly marked as future work?
* Are long paragraphs split into tables or shorter sections?
* Are repeated rules consolidated into the most relevant document?
* Does “agentic” describe language understanding and orchestration without implying
  that the model owns policy or transaction authority?
* Are deterministic confirmation turns and zero-model-call sessions described
  accurately?
* Are actual provider tokens kept distinct from estimated backend payload tokens?

## Final Project Handoff

For presentation and submission preparation, `.ai-context/` should explain:

* The problem: conversational refund handling against strict policy.
* The proof: grounded read tools plus confirmation-gated end-to-end refund execution.
* The safety model: backend policy, persisted consent, guarded transitions, and
  database verification.
* The observability model: per-prompt sessions containing model and deterministic
  execution evidence.
* The limitations: mocked identity, mock funds, and local-first deployment.

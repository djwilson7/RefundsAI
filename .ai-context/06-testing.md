# 06-testing.md

# Testing Standards

## Purpose

Testing is part of implementation. Tests should validate behavior and business rules,
not just execute code for coverage.

Target coverage remains 90% across statements, functions, lines, and branches.

## Validation Commands

Backend:

```bash
cd apps/api
python -m ruff check src tests
python -m pytest tests
python -m pytest tests --cov=refunds_ai_api --cov-report=term-missing --cov-fail-under=90
python -m compileall src tests
```

Frontend:

```bash
npm run lint --workspace @refunds-ai/web
npm run test --workspace @refunds-ai/web
npm run coverage --workspace @refunds-ai/web
npm run build --workspace @refunds-ai/web
```

Root workspace aliases exist for frontend commands, such as `npm run web:test`.

## Current Test Surfaces

Backend tests:

| File | Coverage focus |
| --- | --- |
| `apps/api/tests/test_health.py` | Health response envelope. |
| `apps/api/tests/test_database_health.py` | Database health behavior. |
| `apps/api/tests/test_database_migrator.py` | Migration discovery, status, and seed behavior. |
| `apps/api/tests/test_application_api.py` | User, purchase, details, and refund workflow API behavior. |
| `apps/api/tests/test_refund_policy.py` | Deterministic refund policy decisions. |
| `apps/api/tests/test_model_audit.py` | Audit writer/repository ordering, completion, token metrics, aggregation, and streaming. |
| `apps/api/tests/test_model_audit_api.py` | Admin audit response and SSE contracts. |
| `apps/api/tests/ai_chat/` | Chat endpoint, routing, tools, policy resolution, eligibility, refund mutation, and trace formatting. |

Frontend tests are colocated beside components and route handlers under `apps/web/src`.
They cover API mapping, mock auth, customer screens, detail presentation, help-layer chat,
refund commands, proxy routes, and type-specific cards.

The help-layer tests are split by responsibility:

* `application-help-layer.chat.test.tsx`
* `application-help-layer.refund-commands.test.tsx`
* `application-help-layer.shell.test.tsx`
* `application-help-layer.test-utils.tsx`

## Refund Policy Coverage

Refund workflow tests should validate database-backed policy behavior rather than model
reasoning.

Expected coverage:

* Refund eligibility from `purchases` plus the matching detail table.
* Digital refund windows, redeemed-code blocks, and code invalidation.
* Physical return preparation, carrier acceptance, rejected/cancelled return blocks, and issuance.
* Subscription active-period checks, 48-hour full refund behavior, prorated amount calculation, cancellation, and renewal disabling.
* Prepared state required before fund issuance.
* Already-issued refunds reading persisted amount/outcome facts.
* Duplicate or stale mutations returning workflow denial rather than rewriting state.

## Chat Coverage

Chat tests should validate deterministic orchestration boundaries:

* Compact page and conversation state normalization.
* Object-operation workflow classification.
* Named product, SKU, order number, current page, active purchase, active result set, and ranked follow-up resolution.
* Read-only tool execution for purchase history, date ranges, amount thresholds, policy, and eligibility.
* Response blocking when authoritative tool data is missing.
* Canonical confirmation command requirements for refund process actions.
* Generic confirmations not mutating refund state at the command boundary.
* Customer-facing response guard terms.
* Deterministic confirmation turns preserving audit state while making zero model calls.
* Audit sessions reaching `succeeded` or `failed` rather than remaining `running`.

## Frontend Coverage

Frontend tests should validate rendering and interaction, especially where state crosses
the browser/backend boundary:

* API response mapping in `application-api.ts`.
* Mock login and selected customer session storage.
* Purchase summary storage and fallback behavior.
* Type-specific purchase detail sections.
* Help layer chat state persistence across messages.
* Same-origin proxy routes preserving backend status/body.
* Refund workflow refresh after mutations or chat side effects.
* Admin overview cards showing actual provider tokens only.
* Session detail grouping for identity, process, actual tokens, and estimated tokens.
* Tool-purpose descriptions and narrative event mapping that preserves stored sequence.

## Completion Standard

Before work is complete:

* Run the narrowest meaningful test or lint command.
* State what was validated.
* State any validation that was skipped or incomplete.
* Add or update tests when behavior, contract, policy, or workflow state changes.

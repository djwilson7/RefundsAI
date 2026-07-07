# 03-business-logic.md

# Business Logic

## Business Authority

Business logic is deterministic and backend-owned.

Primary implementation sources:

* `apps/api/src/refunds_ai_api/services/refund_policy.py`
* `apps/api/src/refunds_ai_api/services/refund_policy_catalog.py`
* `apps/api/src/refunds_ai_api/services/application.py`
* `apps/api/src/refunds_ai_api/repositories/application.py`

The language model can ask for policy and eligibility data, but it never enforces
policy itself.

## Policy Catalog vs Workflow Policy

RefundsAI has two policy surfaces:

| Surface | File | Purpose |
| --- | --- | --- |
| Policy catalog | `services/refund_policy_catalog.py` | Customer-facing rule sections for explanation. |
| Workflow policy | `services/refund_policy.py` | Deterministic eligibility, preparation, and issuance decisions. |

Policy catalog output is read-only explanation data. Workflow policy output is the
backend decision used by routes, tools, and services.

## Refund Workflow Model

Refund handling is staged:

```text
eligibility -> preparation -> issuance
```

Workflow stages:

| Stage | Meaning |
| --- | --- |
| `blocked` | Backend policy does not allow refund handling. |
| `eligible` | Backend policy allows the preparation step. |
| `prepared` | The product-specific preparation step has been persisted. |
| `issued` | Mock funds have been issued and final facts are stored on `purchases`. |

Workflow action fields:

| Field | Meaning |
| --- | --- |
| `can_enter_refund_workflow` | The purchase can be discussed as entering refund handling. |
| `can_prepare_refund` | The backend can perform the product-specific preparation mutation. |
| `can_issue_funds` | The backend can finalize mock fund issuance. |
| `required_action` | The next backend action, such as `invalidate_code`, `generate_return_label`, `await_carrier_acceptance`, or `issue_funds`. |

Fund issuance must not skip preparation.

## Product-Specific Policy Facts

Digital:

* Policy facts: `code_redeemed`, `code_redeemed_at`, `code_invalidated_at`,
  `refund_lock_reason`, and `refund_window_expires_at`.
* Preparation: set `code_invalidated_at` and set purchase `status = 'refund_pending'`.
* Issuance gate: purchase is prepared, code was not redeemed, and purchase is not already terminal.

Physical:

* Policy facts: `return_status`, `return_barcode_generated`,
  `return_label_created_at`, `return_requested_at`, `accepted_by_carrier_at`,
  and `refund_window_expires_at`.
* Preparation: set return requested, generated barcode, label timestamp, and purchase
  `status = 'refund_pending'`.
* Issuance gate: return is prepared and `accepted_by_carrier_at` is present.

Subscription:

* Policy facts: `period_start`, `period_end`, `cancelled_at`, `service_ended_at`,
  `auto_renew`, `refund_proration_mode`, `full_refund_window_expires_at`, and
  `refund_window_expires_at`.
* Preparation: set cancellation/service end, disable auto-renew, persist full or
  prorated mode, and set purchase `status = 'refund_pending'`.
* Issuance gate: subscription is prepared and purchase is not already terminal.

Base entry failures include terminal/blocking purchase statuses and expired refund windows.

## Amount and Outcome Rules

Digital and physical refunds are full refunds when eligible.

Subscription refunds are:

* `full` inside the 48-hour full-refund window.
* `prorated` after 48 hours, based on unused time in the active billing period.

Already-issued refunds read `purchases.refund_amount_cents` and
`purchases.refund_outcome`. They must not recompute amount or outcome after
`purchases.status` becomes `refunded`.

Money is stored and compared in cents. Dollar strings are display values.

## Database-Managed Derived Fields

PostgreSQL triggers derive fields that should not be recomputed by the frontend, model,
or API clients:

* Digital `refund_window_expires_at = purchases.purchased_at + 15 days`.
* Digital `code_delivered_at = purchases.purchased_at + 5 minutes` when absent.
* Digital `refund_lock_reason = 'code_redeemed'` when the code is redeemed.
* Physical `refund_window_expires_at = purchases.purchased_at + 30 days`.
* Subscription `full_refund_window_expires_at = purchases.purchased_at + 48 hours`.
* Subscription `refund_window_expires_at = period_end`.
* Subscription cancellation defaults for `auto_renew` and `service_ended_at`.

Backend services should submit event facts and commands, not deadline values.

## Mutation Rules

Repository writes are guarded by expected persisted state.

Examples:

* Digital preparation requires an unredeemed, non-invalidated code and completed purchase.
* Physical preparation requires `return_status = 'not_requested'`, no prior return request, no label, and completed purchase.
* Subscription preparation requires no existing cancellation/service end/proration state and an active completed or subscribed purchase.
* Issuance requires `purchases.status = 'refund_pending'`.
* Carrier acceptance requires a requested physical return and no prior carrier acceptance.

If a guarded update affects anything other than one row, the repository raises
`RepositoryConflictError`. Services map that to `RefundWorkflowError`; routes return a
workflow-specific `409`.

## AI Interaction Rules

The AI assistant may:

* Retrieve policy catalog data.
* Retrieve backend-evaluated refund workflow decisions.
* Explain backend decisions.
* Ask for exact canonical confirmation commands.
* Validate the exact command through the backend confirmation validator.
* Execute refund process actions through backend services only after persisted
  confirmation authorization is granted.
* For digital and subscription purchases, execute confirmed refund handling as:
  prepare, verify prepared state, issue funds, verify issued state.
* For physical purchases, prepare the return process first; fund issuance remains gated
  by carrier acceptance.

The AI assistant may not:

* Calculate eligibility itself.
* Use generic confirmations such as "yes" or "do it" as write approval after a canonical command is required.
* Treat raw message matching or model state as the authority for refund consent.
* Change refund state through an OpenAI-facing write tool.
* Expose internal terms such as graph, resolver, tool, selected state, `issue_funds`, or mutation in customer-facing content.

Refund confirmation consent is backend-owned. The deterministic validator compares
the user message to the expected canonical command, verifies customer ownership,
purchase type, current workflow stage, and required action, then persists exact
consent facts on the purchase detail row. Refund mutations must load that persisted
confirmation and verify it is granted, matched, scoped to the same customer and
purchase, uses the current expected command, and has not already been consumed.

Refund mutations are atomic backend transitions. `request_refund` may only move an
eligible workflow to prepared; `issue_refund` may only move a prepared workflow to
issued. Digital and subscription orchestration may run both transitions after one
valid confirmation, but each transition still gets its own permission check and
persistence validation.

## Frontend Display Rules

Frontend refund display is state visualization only.

* Digital code details remain visible but muted after invalidation; return details show invalidation.
* Physical delivery/tracking remain visible but muted after return preparation; return workflow becomes active.
* Subscription billing cycle remains visible; cancellation and refund facts render in return details.

The frontend must not make header badges or component state authoritative.

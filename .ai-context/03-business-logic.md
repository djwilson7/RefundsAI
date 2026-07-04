# 03-business-logic.md

# Business Logic

## Purpose

This document defines how business logic is organized throughout the system.

Business logic should remain deterministic, modular, and independent of the language model.

The language model may reference business rules through backend tools, but it is not responsible for enforcing them.

---

# Policy Authority

Business policy is the authoritative source for operational decisions.

Policy determines:

* Refund eligibility
* Escalation requirements
* Approval thresholds
* Product-specific behavior
* Administrative review requirements

The database stores the authoritative facts required for policy evaluation, and business services remain responsible for enforcing policy.

Refund state is owned by purchase detail tables:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

No standalone `refunds` table should be introduced.

---

# Policy Organization

Business rules should be organized into independent policy definitions.

Example categories include:

* Physical Product Policy
* Digital Product Policy
* Subscription Policy

Each policy is maintained independently and evaluated according to the purchased item's type.

Each policy consumes the matching purchase detail record:

* Digital policy reads redemption, delivery, invalidation, and lock fields.
* Physical policy reads delivery, return, carrier, and rejection fields.
* Subscription policy reads billing period, cancellation, service end, renewal, and proration fields.

---

# Policy Evaluation

Policy evaluation occurs within deterministic backend services.

The language model never evaluates policy directly.

Instead, the model retrieves policy outcomes through backend tools and communicates those outcomes to customers or administrators.

Refund evaluation flow:

1. User requests refund.
2. Backend loads the purchase.
3. Backend loads the matching purchase detail record.
4. Backend verifies the refund window.
5. Backend evaluates product-specific policy.
6. Backend executes the refund strategy.
7. Backend persists updated refund state to the owning purchase detail table.

Database triggers compute derivable refund fields such as refund window deadlines and default lock/proration fields. Backend services should send event facts and commands, not recompute or transmit values the database can derive from `purchases.purchased_at` or the detail row.

Refund workflow responses distinguish between:

* `can_enter_refund_workflow`: the purchase may enter refund handling.
* `can_prepare_refund`: backend policy permits the product-specific preparation step.
* `can_issue_funds`: backend policy permits mock fund release.

Refund workflow is intentionally staged:

1. Eligibility verifies the policy gate.
2. Preparation mutates the owning purchase detail table into refund-ready state.
3. Issuance finalizes the mock refund by marking the purchase as refunded.

Physical purchases may be prepared before they are issuable because carrier acceptance is required before refund processing begins. Digital purchases are prepared by invalidating the issued entitlement. Subscription purchases are prepared by cancelling service access, disabling renewal, and recording full or prorated refund mode.

Frontend subscription detail pages should reflect this persisted state after preparation without making the header authoritative for subscription state. Active subscriptions show billing-cycle progress under `Billing Cycle Details`. Prepared subscription refunds show `Return Details` with auto-renewal off, days used in the billing cycle, and `Subscription Cancelled`. Issued subscription refunds add cancel date, issued amount, and the expected refund window. This is a presentation of backend state only; the frontend must not decide cancellation, renewal, proration, fund issuance, or refund eligibility independently.

Refund execution must not skip preparation. Fund issuance requires prepared state for every purchase type.

Refund mutations use strict conflict behavior. Duplicate requests, stale reads, or partially prepared state must not silently rewrite timestamps or issue funds. Backend repositories guard each mutation with expected persisted state and raise a repository conflict when the database update does not affect exactly one row. Services map those conflicts to the same workflow-level denial used by the corresponding endpoint.

Issued mock refunds persist final facts on `purchases`: `refunded_at`, `refund_amount_cents`, and `refund_outcome`. Policy evaluation for already-refunded purchases reads these persisted values rather than recomputing after status changes to `refunded`.

---

# Business Services

Business services are responsible for:

* Evaluating policy
* Updating business state
* Updating purchase detail refund lifecycle state
* Preventing duplicate actions
* Recording audit events

Business services remain the authoritative source for operational behavior.

---

# Language Model Interaction

The language model may:

* Retrieve policy information
* Explain policy decisions
* Gather additional customer context
* Execute approved workflows
* Escalate requests when required

The language model may not override deterministic policy decisions.

---

# Policy Sources

Policy definitions should be maintained separately from application code whenever practical.

Business services should reference policy definitions rather than embedding policy directly into model prompts or frontend logic.

This allows policy to evolve independently while maintaining consistent system behavior.

---

# Design Principles

* Business logic remains deterministic.
* Policy enforcement occurs in backend services.
* The database remains the authoritative system of record.
* Refund eligibility is computed from persisted purchase detail state.
* The language model communicates policy rather than defining it.
* Policy should be modular, reusable, and independently maintainable.

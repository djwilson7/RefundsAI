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

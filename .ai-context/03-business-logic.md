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

The database and business services remain responsible for enforcing policy.

---

# Policy Organization

Business rules should be organized into independent policy definitions.

Example categories include:

* Physical Product Policy
* Digital Product Policy
* Subscription Policy

Each policy is maintained independently and evaluated according to the purchased item's type.

---

# Policy Evaluation

Policy evaluation occurs within deterministic backend services.

The language model never evaluates policy directly.

Instead, the model retrieves policy outcomes through backend tools and communicates those outcomes to customers or administrators.

---

# Business Services

Business services are responsible for:

* Evaluating policy
* Updating business state
* Creating refund requests
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
* The language model communicates policy rather than defining it.
* Policy should be modular, reusable, and independently maintainable.

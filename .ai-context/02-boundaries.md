# 02-boundaries.md

# Responsibility Boundaries

## Purpose

This document defines the operational boundaries between users, the frontend, backend services, the language model, and deterministic business logic.

All system behavior should conform to these boundaries.

---

# Customer

Customers may:

* View their own account information.
* View their own purchase history.
* View refund eligibility.
* Request refunds.
* Interact with the AI assistant through text or voice.
* Review their own support history.

Customers may not:

* Access other customer accounts.
* Access administrative functionality.
* Override business policy.
* Modify authoritative business data directly.

---

# Administrator

Administrators may:

* Access the admin dashboard.
* Search for customers.
* Verify customer identity.
* Review customer support history.
* Inspect AI execution logs.
* Review operational metrics.
* Escalate or manually resolve support cases.

Administrator access to customer information is intentionally scoped.

Customer-specific data should only become available after successful customer verification.

---

# Frontend

The frontend is responsible for presentation and user interaction.

The frontend is not an authoritative source for:

* customer information
* purchase data
* refund eligibility
* policy decisions
* financial state
* refund lifecycle state

Business data should always be retrieved through backend APIs.

---

# Backend

The backend is the authoritative application layer.

The backend is responsible for:

* business services
* policy enforcement
* AI orchestration
* tool execution
* audit logging
* database communication
* loading purchase detail state for refund evaluation
* persisting approved refund lifecycle updates to the owning detail table

The backend is the only layer permitted to communicate with external AI services and the database.

---

# Language Model

The language model is responsible for:

* conversation
* intent recognition
* context gathering
* backend tool orchestration
* customer communication
* administrator communication
* intelligent escalation

The language model may automate business workflows only when deterministic policy explicitly permits the requested action.

The language model is not the authoritative source for:

* refund eligibility
* refund lifecycle state
* customer records
* financial state
* business policy
* operational decisions

Authoritative information must always be retrieved through backend tools.

---

# Business Policy

Business policy is the authoritative source for operational decisions.

Refund eligibility is determined from persisted database facts plus deterministic backend policy evaluation. The database owns the state required to evaluate policy; backend services own the evaluation and valid state transitions.

Policy determines:

* refund eligibility
* refund limits
* escalation requirements
* approval thresholds
* product-specific rules

Neither the frontend nor the language model may override business policy.

No standalone `refunds` table should be introduced. Refund state belongs to `digital_purchase_details`, `physical_purchase_details`, or `subscription_purchase_details` depending on the purchase type.

---

# Authentication

Authentication is intentionally mocked.

The objective of this project is AI orchestration rather than production identity management.

Authentication boundaries exist to demonstrate user separation, not production authentication.

The frontend mock authentication route (`/`) may select seeded mock identities and store local UI session hints in browser session storage. That state is only a presentation aid for local frontend development. It must not be treated as an authenticated backend session, an authorization source, or an authoritative source for customer data.

Customer home routing should carry the selected mock customer identifier in the URL (`/user-home?customerId={customerId}`) so refreshes render the same mock identity on the server and client. Backend APIs remain responsible for all future authoritative customer, purchase, refund, policy, and support data.

---

# Escalation

The language model should resolve requests whenever policy permits.

The language model should escalate interactions when:

* policy requires human review
* customer requests a human representative
* customer behavior becomes abusive or hostile
* fraud or unusual activity is suspected
* business policy cannot determine a valid outcome

Escalation should preserve the complete interaction history for administrator review.

---

# System Authority

System authority follows this hierarchy:

```text
Business Policy
        │
        ▼
Business Services
        │
        ▼
Database
        │
        ▼
Backend
        │
        ▼
Language Model
        │
        ▼
Frontend
```

Each layer should operate only within its defined responsibilities.

## Refund Authority

For refund workflows, the authority order is:

```text
Database detail state
-> Business policy
-> Business services
-> Backend APIs and tools
-> Language model
-> Frontend
```

The purchase detail tables hold the facts. Backend services apply policy to those facts. The language model and frontend receive evaluated outcomes only.

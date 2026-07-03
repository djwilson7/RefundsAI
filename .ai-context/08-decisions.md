# 08-decisions.md

# Architectural Decisions

## Purpose

This document records significant architectural and implementation decisions made throughout the project.

Its purpose is to preserve engineering intent, prevent unnecessary refactoring, and provide context for future contributors.

Record decisions when they establish long-term architecture, implementation boundaries, or intentional tradeoffs.

---

# Decision Template

## Decision XXX: Title

### Decision

What was decided?

### Reason

Why was this decision made?

### Consequence

How does this decision affect future development?

---

# Decision 001: Mock Authentication

### Decision

Customer and administrator authentication is implemented as a mocked workflow.

### Reason

This project evaluates AI product behavior, deterministic business logic, and customer support workflows rather than production authentication.

### Consequence

Authentication boundaries are demonstrated without introducing unnecessary identity infrastructure. Production authentication should not be added unless project scope changes.

---

# Decision 002: Deterministic Policy Enforcement

### Decision

Refund eligibility and business policy are enforced through backend services rather than the language model.

### Reason

Business decisions must remain deterministic, auditable, and consistently enforceable.

### Consequence

The language model communicates policy outcomes but never becomes the authority for operational decisions.

---

# Decision 003: Desktop-First Experience

### Decision

The application targets desktop web as the primary platform.

### Reason

Development effort is intentionally focused on demonstrating AI product behavior rather than cross-platform responsiveness.

### Consequence

Mobile optimization remains outside the current project scope.

---

# Decision 004: Documentation-First Development

### Decision

Repository knowledge is maintained within the `.ai-context/` directory.

### Reason

Both human contributors and AI agents require a centralized, authoritative source of project context.

### Consequence

Architectural changes should be reflected in `.ai-context/` as part of implementation to keep documentation synchronized with the codebase.

---

# Decision 005: Identity Layer Established

### Decision

The system uses a normalized identity model consisting of `users`, `roles`, and `user_roles`.

### Reason

This separates identity from permissions while avoiding duplicated customer/admin tables. The schema supports mocked authentication today while remaining compatible with future production authentication.

### Consequence

All future domain entities reference `users.id` as the authoritative owner. Role-based behavior is determined through `user_roles`, allowing the application to distinguish customer and administrator experiences without embedding role information directly into the `users` table.

---

# Decision 006: Consolidated Mock Product Catalog

### Decision

The project uses one consolidated `products` table for physical products, digital products, and subscription offerings. Product and purchase seed data is mocked with enough variety and distribution to approximate real customer purchase history:

* 14 physical products
* 10 digital products
* 6 subscription products
* 180 seeded purchases across 15 customer users
* purchase distribution weighted toward physical products, then digital products, then subscriptions

### Reason

RefundsAI needs realistic catalog and purchase-history data for the customer UI, admin views, reporting, and agent responses. For this project, a universal limited catalog table keeps the schema understandable while still providing enough variety to mimic real-world customer behavior.

In a production catalog, physical inventory, digital goods, and subscriptions would likely deserve separate tables or subtype-specific structures because they have different operational metadata, lifecycle rules, fulfillment concerns, and expected volume. This project intentionally avoids that additional catalog complexity until the product scope requires it.

### Consequence

Product-specific behavior should use `products.product_type` and `purchases.purchase_type` rather than introducing separate product tables during the current scope. The mock catalog should remain intentionally limited and representative, not a full ecommerce inventory model. If future scope requires production-scale catalog behavior, split product types into more specialized tables or subtype models before adding complex inventory, entitlement, or subscription metadata.

---

# Decision 007: Purchase Detail Extension Tables

### Decision

Type-specific mutable purchase fields are stored in one-to-one detail tables:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

Each table references `purchases(id)` through a unique `purchase_id`, making it an extension of the base purchase record.

### Reason

Digital purchases, physical purchases, and subscription purchases need different operational fields. Digital purchases need code issuance and redemption state. Physical purchases need delivery, carrier, tracking, and return flow state. Subscriptions need period and cancellation state.

Keeping all of those fields on `purchases` would turn the primary purchase table into a nullable god table with many columns that only apply to one product type. Splitting detail data by purchase type keeps the base table focused on shared purchase history while preserving tailored fields for each purchase workflow.

### Consequence

The application should treat `purchases` as the shared lookup and history table, then load exactly one matching detail row based on `purchases.purchase_type`. For v1.0, cross-table exclusivity is validated in seed tests and backend service logic rather than enforced through database triggers. If production scope requires stronger guarantees, add database-level enforcement after the service behavior is stable.

Physical delivery timing is a narrower integrity rule and is enforced in the database with a trigger because it compares `physical_purchase_details` values against `purchases.purchased_at`. This preserves the decision to avoid cross-table exclusivity triggers while still keeping delivery-window rules authoritative.

---

# Decision 008: Refund State Lives in Purchase Detail Tables

### Decision

Refund state is embedded in the product-type-specific purchase detail tables instead of using a standalone `refunds` table.

The owning tables are:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

The shared `purchases` table remains purchase history and should not duplicate refund lifecycle state.

### Reason

Refund policy depends on different facts for each product type. Digital purchases depend on code delivery, redemption, invalidation, and refund lock reasons. Physical purchases depend on delivery, return authorization, carrier acceptance, receipt, and rejection state. Subscriptions depend on billing period, cancellation, service end, renewal, and proration state.

Embedding those facts in the detail table that owns the product lifecycle avoids duplicated state, keeps ownership with the purchase type, simplifies policy evaluation, makes SQL state authoritative, reduces synchronization problems, and allows backend services and AI tools to consume the same database-backed facts.

### Consequence

No standalone `refunds` table should be introduced under the current architecture. Refund eligibility is computed by backend policy services from `purchases` plus the matching purchase detail record. AI tools expose evaluated information from backend services and must not ask the model to infer eligibility from partial context.

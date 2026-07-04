# 10-database.md

# Database Schema

## Purpose

This document defines the database schema, entity relationships, data ownership, and schema evolution throughout the project.

The database remains the authoritative source for all persistent business state.

---

# Database Principles

* The database is the system of record.
* The database is the source of truth for refund eligibility facts.
* Business services own all database interactions.
* The frontend never communicates directly with the database.
* The language model retrieves database information exclusively through backend tools.
* Refund lifecycle state is owned by purchase detail tables, not by a standalone `refunds` table.
* No duplicate refund state should be introduced outside the owning purchase detail table.

---

# Entity Documentation

Each entity should document:

* Purpose
* Owner
* Relationships
* Frontend Visibility
* Backend Visibility

Example:

```text id="52lzww"
customers

Purpose
Stores customer account information.

Owner
Backend

Relationships
orders
support_sessions
account_ledger

Frontend
Customer profile information only.

Backend
Full record.
```

# Identity Layer

The identity layer defines human actors in the mock CRM system.

## Tables

* `users`
* `roles`
* `user_roles`

## Identity Relationship

`users` connects to `roles` through `user_roles`.

```text
users
  -> user_roles
       -> roles
```

```text
users.id -> user_roles.user_id
roles.id -> user_roles.role_id
```

This creates a many-to-many relationship:

* one user can have many roles
* one role can belong to many users

For v1.0, each seeded user has one role. The join table keeps the schema flexible without adding production authentication complexity.

## users

Purpose
Owns the human entity and stores only identity basics.

Owner
Backend

Columns
`id`, `first_name`, `last_name`, `created_at`

Belongs Here
Who the person is.

Does Not Belong Here
Authentication data, email, password, avatar, store credit, purchase metadata, support metadata, or admin-only metadata.

Relationships
`users.id` -> `user_roles.user_id`

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

## roles

Purpose
Owns role definitions used to determine which mock interface a user enters.

Owner
Backend

Columns
`id`, `key`, `name`

Belongs Here
Role definitions such as `customer` and `admin`.

Does Not Belong Here
Permissions matrices, feature flags, or authentication logic.

Relationships
`roles.id` -> `user_roles.role_id`

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

## user_roles

Purpose
Owns the many-to-many assignment between a user and a role.

Owner
Backend

Columns
`user_id`, `role_id`, `created_at`

Belongs Here
Assignments such as `John Smith -> customer` and `System Administrator -> admin`.

Relationships
`user_roles.user_id` references `users(id)` with `on delete cascade`.
`user_roles.role_id` references `roles(id)` with `on delete cascade`.

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

## Identity Relationship Rules

`users -> user_roles`

```sql
user_roles.user_id references users(id) on delete cascade
```

If a mock user is deleted, their role assignments should disappear.

`roles -> user_roles`

```sql
user_roles.role_id references roles(id) on delete cascade
```

If a role is removed, assignments for that role should disappear.

Uniqueness:

```sql
primary key (user_id, role_id)
```

This prevents duplicate role assignments.

## Identity Seed Data

The initial seed includes:

* 15 customer users
* 1 administrator user
* 2 roles: `customer`, `admin`
* 16 role assignments

The executable seed fixture lives at `apps/api/mockdata/identity_seed.json`.

Recommended role values:

```text
key: customer
name: Customer

key: admin
name: Administrator
```

The `users` seed includes exactly 16 rows: 15 customers and 1 administrator. User seed rows include `first_name`, `last_name`, and `created_at`.

The `user_roles` seed includes exactly 16 rows: 15 assignments to `customer` and 1 assignment to `admin`.

Identity seed data is deterministic and idempotent. Roles and users are upserted by stable identifiers or keys, and role assignments use the `primary key (user_id, role_id)` constraint to prevent duplicates.

## Identity Query Patterns

Mock customer login:

```text
select users
join user_roles
join roles
where roles.key = 'customer'
```

Displays selectable customer profiles.

Mock admin login:

```text
select users
join user_roles
join roles
where roles.key = 'admin'
```

Displays the single admin profile.

Role check:

```text
given user_id
-> lookup assigned roles
-> determine portal access
```

Authentication, permissions, purchases, support history, and financial state are intentionally excluded from this layer.

---

# Purchase Catalog Layer

The purchase catalog layer defines what can be purchased and records customer-owned purchase history.

## Tables

* `products`
* `purchases`

## Purchase Relationship

```text
users
  -> purchases
       -> products
```

```text
users.id -> purchases.user_id
products.id -> purchases.product_id
```

## products

Purpose
Catalog reference for what was purchased.

Owner
Backend

Columns
`id`, `name`, `sku`, `product_type`, `base_price_cents`, `created_at`, `updated_at`

Constraints
`product_type` must be one of `physical`, `digital`, or `subscription`.
`base_price_cents` must be greater than or equal to zero.
`sku` is unique through `products_sku_idx`.

Relationships
`products.id` -> `purchases.product_id`

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

## purchases

Purpose
Customer-owned purchase history and primary lookup table.

Owner
Backend

Columns
`id`, `user_id`, `product_id`, `order_number`, `purchase_type`, `amount_cents`, `purchased_at`, `status`, `refund_requested_at`, `refunded_at`, `refund_amount_cents`, `refund_outcome`, `created_at`, `updated_at`

Constraints
`purchase_type` must be one of `physical`, `digital`, or `subscription`.
`status` must be one of `completed`, `subscribed`, `redeemed`, `refund_pending`, `refunded`, or `cancelled`.
`amount_cents` must be greater than or equal to zero.
`refund_amount_cents` must be null or greater than or equal to zero.
`refund_outcome` must be null, `full`, or `prorated`.
`order_number` is unique through `purchases_order_number_idx`.

Relationships
`purchases.user_id` references `users(id)` with `on delete cascade`.
`purchases.product_id` references `products(id)`.

Important Rule
`purchases.purchase_type` mirrors `products.product_type` at purchase time. If product catalog metadata changes later, historical purchase records keep their original purchase type.

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

Refund State Boundary
`purchases.status` is a workflow summary used for purchase cards and broad lifecycle filtering. Product-type-specific refund state such as digital entitlement invalidation, physical return progress, and subscription cancellation or proration belongs to the matching purchase detail table.

Issued Refund Facts
`refund_requested_at` records the successful backend preparation timestamp. `refunded_at`, `refund_amount_cents`, and `refund_outcome` record the final mock fund issuance facts. Already-refunded policy decisions must read these persisted values rather than recomputing refund amount or outcome.

Refund Mutation Guards
Refund workflow writes are guarded with expected SQL state. Duplicate calls, stale reads, and partial lifecycle state should affect zero rows and raise a repository conflict, causing the surrounding transaction to roll back.

## Purchase Query Patterns

Customer purchase history:

```sql
select
  purchases.id,
  purchases.order_number,
  purchases.purchase_type,
  purchases.amount_cents,
  purchases.purchased_at,
  purchases.status,
  products.name,
  products.sku
from purchases
join products on products.id = purchases.product_id
where purchases.user_id = :user_id
order by purchases.purchased_at desc;
```

## Purchase Seed Data

The product and purchase fixture lives at `apps/api/mockdata/purchase_seed.json`.

The product catalog seed includes:

* 14 physical products
* 10 digital products
* 6 subscription products

The generated purchase history includes 180 deterministic purchases across 15 customer users, with each customer receiving 12 purchases.

All seeded purchases are active and use `status = 'completed'`. Seeded purchase dates generally fall within the recent 45-day window from 2026-05-20 through 2026-07-03 so refund behavior can be tested against relevant transaction history. Digital purchases are intentionally constrained to 2026-06-20 through 2026-07-04 so no seeded digital purchase is future-dated while the database-derived 15-day refund window remains testable after the current development date.

Purchase type distribution:

* 90 physical purchases
* 54 digital purchases
* 36 subscription purchases

Purchase seed data is deterministic and idempotent. Products are upserted by SKU. Purchases are upserted by `order_number`, and `purchases.purchase_type` is copied from the product type at purchase generation time.

## Purchase Detail Seed Data

The purchase detail seed step derives one detail row from every deterministic purchase:

* 54 `digital_purchase_details` rows
* 90 `physical_purchase_details` rows
* 36 `subscription_purchase_details` rows

Digital purchase detail rows issue one unique code per digital purchase. Most codes remain unredeemed, some are marked redeemed, and `code_invalidated_at` remains null. Database triggers populate `code_delivered_at`, `refund_window_expires_at`, and the DB-derived `refund_lock_reason` for redeemed codes.

Physical purchase detail rows set `scheduled_delivery_at`, keep `return_status = 'not_requested'`, and populate carrier and tracking values. `delivered_at` is set only when `scheduled_delivery_at` is on or before the detail seed reference time; future scheduled deliveries keep `delivered_at` null. Database triggers populate `refund_window_expires_at`.

Subscription purchase detail rows set `period_start` to `purchased_at` and set `period_end` to 30 days after `purchased_at`. Database defaults and triggers populate cancellation defaults, `full_refund_window_expires_at`, and `refund_window_expires_at`.

The seed validator confirms detail row counts match purchase counts by type, each purchase receives exactly one matching type detail row, no purchase receives multiple type detail rows, digital issued codes are unique, physical delivery timestamps obey the delivery-window rules, and subscription periods are ordered correctly.

## Purchase Detail Extensions

Purchase detail tables are one-to-one extensions of `purchases`. They hold mutable fields that only apply to a specific purchase type.

```text
purchases.id
  -> digital_purchase_details.purchase_id
  -> physical_purchase_details.purchase_id
  -> subscription_purchase_details.purchase_id
```

Each purchase should have exactly one detail row matching `purchases.purchase_type`:

```text
digital -> digital_purchase_details
physical -> physical_purchase_details
subscription -> subscription_purchase_details
```

For v1.0, cross-table exclusivity is not enforced with database triggers. Seed tests and backend service logic should validate that detail rows match purchase type.

## digital_purchase_details

Purpose
Mutable lifecycle state for digital purchases, including code issuance, redemption, invalidation, and refund-blocking facts.

Owner
Backend

Columns
`id`, `purchase_id`, `issued_code`, `code_redeemed`, `code_redeemed_at`, `code_invalidated_at`, `code_delivered_at`, `refund_window_expires_at`, `refund_lock_reason`, `created_at`, `updated_at`

Constraints
`issued_code` must be unique.
`code_redeemed` defaults to `false`.
If `code_redeemed = true`, `code_redeemed_at` must be present.
`code_invalidated_at` and `refund_lock_reason` may be null.
`code_delivered_at` and `refund_window_expires_at` are database-managed and required after trigger backfill.

Database-Managed Fields
On insert or relevant update, `set_digital_purchase_refund_fields` derives:

* `refund_window_expires_at = purchases.purchased_at + 15 days`
* `code_delivered_at = purchases.purchased_at + 5 minutes` when not explicitly provided
* `refund_lock_reason = 'code_redeemed'` when `code_redeemed = true`

Refund Rules
Digital refund policy depends on persisted detail state:

* A digital purchase can be considered for refund only if the code has not been redeemed.
* If a refund is approved, the issued code is invalidated by setting `code_invalidated_at`.
* If `code_redeemed = true`, `refund_lock_reason` should explain the refund block.
* If `code_invalidated_at` is present, the code should no longer be usable.

Relationships
`digital_purchase_details.purchase_id` references `purchases(id)` with `on delete cascade`.

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

## physical_purchase_details

Purpose
Mutable lifecycle state for physical purchases, including delivery, return authorization, carrier acceptance, and return completion facts.

Owner
Backend

Columns
`id`, `purchase_id`, `scheduled_delivery_at`, `delivered_at`, `return_status`, `carrier`, `tracking_number`, `return_barcode_generated`, `return_label_created_at`, `accepted_by_carrier_at`, `return_requested_at`, `return_authorized_at`, `return_received_at`, `return_rejected_at`, `return_rejection_reason`, `refund_window_expires_at`, `created_at`, `updated_at`

Constraints
`return_status` must be one of `not_requested`, `requested`, `authorized`, `accepted_by_carrier`, `received`, `rejected`, or `cancelled`.
If `return_status = 'rejected'`, `return_rejected_at` and `return_rejection_reason` must be present.

Delivery timing is validated against the owning `purchases.purchased_at` value:

* `scheduled_delivery_at` must be after `purchased_at`.
* `scheduled_delivery_at` must be between `purchased_at + 2 days` and `purchased_at + 7 days`.
* `delivered_at` may be null.
* When present, `delivered_at` must be after `purchased_at`.
* When present, `delivered_at` must be on or before `scheduled_delivery_at`.
* When present, `delivered_at` must be on or before `now()`.

These delivery timing rules are enforced through a trigger because PostgreSQL table check constraints cannot reference `purchases.purchased_at`.

Database-Managed Fields
On insert or relevant update, `set_physical_purchase_refund_fields` derives:

* `refund_window_expires_at = purchases.purchased_at + 30 days`

Return Lifecycle Rules

* `return_requested_at` may be null until the customer requests a return.
* `return_barcode_generated` defaults to false and becomes true when the backend prepares a physical return.
* `return_label_created_at` may be null until the backend prepares a physical return.
* `return_authorized_at` may be null until the backend authorizes the return.
* `accepted_by_carrier_at` may be null until the carrier accepts the returned item.
* `return_received_at` may be null until the returned item is received.
* `return_rejected_at` may be null unless the return is rejected.
* `return_rejection_reason` may be null unless the return is rejected.

Refund Rules
Physical refund policy depends on persisted detail state:

* A physical purchase can be considered for refund if it is within the 30-day refund window and return state satisfies policy.
* The return package must be accepted by the designated carrier before the refund begins processing.
* For v1.0, the primary processing gate is `accepted_by_carrier_at is not null`.
* If the return is rejected, `return_status` should be `rejected`, `return_rejected_at` should be present, and `return_rejection_reason` should explain why.

Relationships
`physical_purchase_details.purchase_id` references `purchases(id)` with `on delete cascade`.

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

## subscription_purchase_details

Purpose
Mutable lifecycle state for subscription purchases, including billing period, cancellation, service end, renewal, and refund-proration facts.

Owner
Backend

Columns
`id`, `purchase_id`, `period_start`, `period_end`, `cancelled_at`, `service_ended_at`, `auto_renew`, `refund_proration_mode`, `full_refund_window_expires_at`, `refund_window_expires_at`, `created_at`, `updated_at`

Constraints
`period_end` must be greater than `period_start`.
`auto_renew` defaults to `true`.
`refund_proration_mode` must be one of `none`, `full`, or `prorated`.
`full_refund_window_expires_at` and `refund_window_expires_at` are database-managed and required after trigger backfill.

Database-Managed Fields
On insert or relevant update, `set_subscription_purchase_refund_fields` derives:

* `full_refund_window_expires_at = purchases.purchased_at + 48 hours`
* `refund_window_expires_at = period_end`
* `auto_renew = false` when `cancelled_at` is present
* `service_ended_at = cancelled_at` when cancellation is present and no service end is explicitly provided

Refund Rules
Subscription refund policy depends on persisted detail state:

* A subscription can be considered for refund only while the current billing period is active.
* A subscription is active when the evaluation timestamp is greater than or equal to `period_start` and less than or equal to `period_end`.
* Full refunds may be available inside the initial 48-hour window when the subscription remains active.
* After 48 hours, eligible refunds are calculated from unused time in the current active billing period.
* If a refund is approved, the backend may set `cancelled_at`, `service_ended_at`, `auto_renew = false`, and `refund_proration_mode`.

Relationships
`subscription_purchase_details.purchase_id` references `purchases(id)` with `on delete cascade`.

Frontend
Only fields returned through documented backend APIs.

Backend
Full record.

---

# Relationships

Document relationships between entities as they are introduced.

Example:

```text id="t11z5l"
Customer
    │
    ├── Orders
    │      └── Order Items
    │               └── Purchase Detail State
    │
    ├── Support Sessions
    │      └── Support Messages
    │
    ├── Account Ledger
    │
    └── AI Events
```

---

# Frontend Data

Only data required by the user interface should be exposed through backend APIs.

Sensitive or internal fields should remain backend-only.

---

# Backend Data

Internal business state, audit information, policy metadata, and implementation-specific fields remain accessible only through backend services.

---

# Schema Changes

Structural database changes should be recorded here.

Document:

* Date
* Change
* Reason

Example:

```text id="c6x1js"
2026-07-03

Added refund policy fields to purchase detail tables.

Reason

Support deterministic policy evaluation without requiring the language model to infer refund state.
```

2026-07-03

Added backend-owned database migration infrastructure.

Reason

Provide a reproducible entry point for creating Supabase PostgreSQL tables, indexes, primary keys, foreign keys, row-level security policies, and seed data without allowing the frontend or language model to access the database directly.

2026-07-03

Added users table.

Reason

Establish the first root application identity table for later customer, administrator, purchase, support, and refund workflow relationships.

2026-07-03

Added roles table.

Reason

Establish stable role definitions before introducing user-to-role relationships and role-scoped workflow behavior.

2026-07-03

Added user_roles table.

Reason

Connect users to roles through a constrained many-to-many relationship before role-scoped backend workflows are introduced.

2026-07-03

Clarified identity layer contract.

Reason

Document table ownership, many-to-many role assignment behavior, cascade rules, seed expectations, query patterns, and exclusions before applying identity migrations.

2026-07-03

Added identity seed fixture and seed execution.

Reason

Populate the mock identity layer with deterministic users, roles, and assignments for customer and administrator interface configuration.

2026-07-03

Defined products and purchases migrations.

Reason

Add the catalog reference and customer purchase history schema definitions before deploying the next database migration pass.

2026-07-03

Added product and purchase seed fixture and execution.

Reason

Populate the catalog and customer purchase history with deterministic mock data for future UI, admin, reporting, and AI interaction workflows.

2026-07-03

Defined purchase detail extension migrations.

Reason

Move product-type-specific mutable purchase state into one-to-one detail tables instead of adding nullable type-specific fields to `purchases`.

2026-07-03

Updated physical purchase detail delivery timing contract.

Reason

Add `scheduled_delivery_at` and database-enforced delivery-window validation so physical purchase seed data and refund workflows can model recent delivery state consistently.

2026-07-03

Added purchase detail seed generation and execution.

Reason

Populate product lifecycle state for digital codes, physical delivery state, and subscription periods before active refund workflows are introduced.

2026-07-03

Embedded refund state into purchase detail tables.

Reason

Make the database authoritative for refund eligibility by storing product-type-specific refund facts on `digital_purchase_details`, `physical_purchase_details`, and `subscription_purchase_details`, while preventing duplicate refund state in `purchases` or a standalone `refunds` table.

2026-07-03

Added database-managed refund deadline triggers.

Reason

Compute refund deadlines and derivable refund defaults inside PostgreSQL so backend seed and future service calls only send event facts, while the database owns deadline calculation and derived refund fields.

2026-07-03

Added refund workflow preparation state.

Reason

Represent refund lifecycle as eligibility, preparation, and issuance stages. Re-expanded purchase status as a workflow summary and added physical return preparation fields for simulated return barcode and label creation.

2026-07-03

Added persisted refund issue facts and guarded mutation expectations.

Reason

Prevent duplicate or stale refund workflow mutations from rewriting timestamps or issuing ghost credits. `purchases` now records refund request and issued refund facts, while repository writes guard expected lifecycle state and treat rowcount mismatches as conflicts.

--- 

# Migration Philosophy

Schema changes should preserve data integrity whenever practical.

Every migration should be accompanied by corresponding updates to:

* Database documentation
* API contracts
* Business logic documentation
* Tests (when applicable)

## Migration Entry Point

Database schema changes are applied through the backend package:

```bash
cd apps/api
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator apply
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator status
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator seed
```

Migration modules live in `apps/api/src/refunds_ai_api/database/migrations/`.

Each table should be introduced by one ordered migration module. Migration modules should expose:

* `MIGRATION_ID`
* `DESCRIPTION`
* `upgrade(connection)`
* `create_table(connection)`
* `create_indexes(connection)`
* `enable_rls(connection)`
* `create_policies(connection)`

The migration runner records applied migrations in `schema_migrations`, which is internal metadata and not business data.

Business seed data lives in `apps/api/src/refunds_ai_api/database/seeds.py`. Seed steps should be idempotent and should only be added after the schema they depend on exists.

## Table Creation Requirements

Every business-data table should define:

* primary keys in `create_table`
* foreign keys in `create_table`
* uniqueness and check constraints in `create_table`
* query-performance indexes in `create_indexes`
* row-level security in `enable_rls`
* explicit RLS policies in `create_policies`

The frontend must continue to receive data only through backend APIs. The language model must continue to retrieve database-backed information only through backend tools and services.

---

# Development Foundation Connectivity

The backend reads Supabase PostgreSQL connectivity from `SUPABASE_DB_URL`.

`GET /health/database` performs a non-mutating database handshake by executing `select 1 as ok`.

This confirms that:

* database environment configuration is present
* the backend can reach Supabase PostgreSQL
* credentials are valid enough to open a connection

This does not introduce schema, migrations, seed data, business tables, or Supabase client access from the frontend.

# 10-database.md

# Database Schema

## Purpose

This document defines the database schema, entity relationships, data ownership, and schema evolution throughout the project.

The database remains the authoritative source for all persistent business state.

---

# Database Principles

* The database is the system of record.
* Business services own all database interactions.
* The frontend never communicates directly with the database.
* The language model retrieves database information exclusively through backend tools.

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
`id`, `user_id`, `product_id`, `order_number`, `purchase_type`, `amount_cents`, `purchased_at`, `status`, `created_at`, `updated_at`

Constraints
`purchase_type` must be one of `physical`, `digital`, or `subscription`.
`status` must be one of `completed`, `refund_pending`, `refunded`, or `cancelled`.
`amount_cents` must be greater than or equal to zero.
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

Purchase type distribution:

* 90 physical purchases
* 54 digital purchases
* 36 subscription purchases

Purchase seed data is deterministic and idempotent. Products are upserted by SKU. Purchases are upserted by `order_number`, and `purchases.purchase_type` is copied from the product type at purchase generation time.

---

# Relationships

Document relationships between entities as they are introduced.

Example:

```text id="t11z5l"
Customer
    │
    ├── Orders
    │      └── Order Items
    │               └── Refund Eligibility
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

Added refund_eligibility table.

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

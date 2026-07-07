# 10-database.md

# Database Schema

## Purpose

This document defines the PostgreSQL schema, data ownership, migrations, seed data,
and database-managed refund facts.

Implementation source:

* Migrations: `apps/api/src/refunds_ai_api/database/migrations/`
* Migrator: `apps/api/src/refunds_ai_api/database/migrator.py`
* Seeds: `apps/api/src/refunds_ai_api/database/seeds.py`
* Identity fixture: `apps/api/mockdata/identity_seed.json`
* Product/purchase fixture: `apps/api/mockdata/purchase_seed.json`

## Database Principles

* PostgreSQL is the persistent system of record.
* Backend repositories are the only application code that reads or writes the database.
* The frontend must not connect to Supabase directly.
* The language model must retrieve database-backed facts only through backend services and tools.
* Refund lifecycle facts live in purchase detail tables.
* `purchases` stores shared purchase facts and final issued refund facts.
* No standalone `refunds` table should be introduced under the current architecture.

## Schema Layers

| Layer | Tables | Purpose |
| --- | --- | --- |
| Migration metadata | `schema_migrations` | Tracks applied migration ids. |
| Identity | `users`, `roles`, `user_roles` | Mock users and role assignments. |
| Catalog/history | `products`, `purchases` | Product reference and customer purchase history. |
| Detail extensions | `digital_purchase_details`, `physical_purchase_details`, `subscription_purchase_details` | Type-specific lifecycle and refund facts. |
| Model audit | `model_audit_sessions`, `model_audit_events`, `model_audit_event_lookup` | AI chat audit session headers, ordered events, and normalized event-key metadata. |

## Identity Layer

Relationship:

```text
users.id -> user_roles.user_id
roles.id -> user_roles.role_id
```

### `users`

Purpose: Stores human identity basics.

Columns:

* `id`
* `first_name`
* `last_name`
* `created_at`

Does not store authentication data, email, password, customer metadata, purchase data,
or admin-specific metadata.

### `roles`

Purpose: Stores stable role definitions for mock entry paths.

Columns:

* `id`
* `key`
* `name`

Current role keys:

* `customer`
* `admin`

### `user_roles`

Purpose: Assigns users to roles.

Columns:

* `user_id`
* `role_id`
* `created_at`

Rules:

* Primary key: `(user_id, role_id)`
* `user_id` cascades on user delete.
* `role_id` cascades on role delete.

For v1.0, each seeded user has one role. The join table exists so role behavior does
not have to be duplicated onto `users`.

## Catalog and Purchase History

Relationship:

```text
users.id -> purchases.user_id
products.id -> purchases.product_id
```

### `products`

Purpose: Mock catalog reference.

Columns:

* `id`
* `name`
* `sku`
* `product_type`
* `base_price_cents`
* `created_at`
* `updated_at`

Rules:

* `product_type` is `physical`, `digital`, or `subscription`.
* `base_price_cents >= 0`.
* `sku` is unique.

### `purchases`

Purpose: Customer-owned purchase history and shared workflow summary.

Columns:

* `id`
* `user_id`
* `product_id`
* `order_number`
* `purchase_type`
* `amount_cents`
* `purchased_at`
* `status`
* `refund_requested_at`
* `refunded_at`
* `refund_amount_cents`
* `refund_outcome`
* `created_at`
* `updated_at`

Rules:

* `purchase_type` is `physical`, `digital`, or `subscription`.
* `status` is `completed`, `subscribed`, `redeemed`, `refund_pending`, `refunded`, or `cancelled`.
* `amount_cents >= 0`.
* `refund_amount_cents` is null or non-negative.
* `refund_outcome` is null, `full`, or `prorated`.
* `order_number` is unique.

`purchases.purchase_type` mirrors `products.product_type` at purchase time so historical
purchases keep their original type even if product catalog metadata changes later.

Refund boundary:

* `status` is a broad workflow summary.
* `refund_requested_at` records successful preparation.
* `refunded_at`, `refund_amount_cents`, and `refund_outcome` record final mock issuance facts.
* Product-specific lifecycle state stays in the matching detail table.

## Purchase Detail Extensions

Relationship:

```text
purchases.id
  -> digital_purchase_details.purchase_id
  -> physical_purchase_details.purchase_id
  -> subscription_purchase_details.purchase_id
```

Each purchase should have exactly one detail row matching `purchases.purchase_type`.
For v1.0, this is validated by seed tests and backend service logic rather than a
cross-table exclusivity trigger.

### Shared Refund Confirmation Fields

Migration `013_add_refund_confirmation_state.py` adds backend-owned confirmation
authorization facts to all purchase detail tables:

* `refund_confirmation_granted`
* `refund_confirmation_message`
* `refund_confirmation_granted_at`
* `refund_confirmation_expected_command`
* `refund_confirmation_matched`
* `refund_confirmation_source`
* `refund_confirmation_customer_id`
* `refund_confirmation_purchase_id`
* `refund_confirmation_consumed_at`
* `refund_confirmation_consumed_by_action`

These fields preserve the exact user message, grant timestamp, expected command,
target customer, target purchase, deterministic match result, and optional consumption
facts for the active refund workflow. They belong on detail rows because this project
does not model refunds as a separate aggregate table.

Only the backend confirmation validator may set `refund_confirmation_granted = true`.
Mutation execution must treat these fields as authorization facts, not presentation
state.

### `digital_purchase_details`

Purpose: Digital entitlement lifecycle and refund-blocking facts.

Columns:

* `id`
* `purchase_id`
* `issued_code`
* `code_redeemed`
* `code_redeemed_at`
* `code_invalidated_at`
* `code_delivered_at`
* `refund_window_expires_at`
* `refund_lock_reason`
* `created_at`
* `updated_at`

Rules:

* `issued_code` is unique.
* Redeemed codes require `code_redeemed_at`.
* Trigger derives `code_delivered_at`, `refund_window_expires_at`, and redeemed-code lock reason.

Policy use:

* Redeemed codes block refund handling.
* Approved digital preparation invalidates the code.

### `physical_purchase_details`

Purpose: Physical fulfillment, return workflow, and carrier facts.

Columns:

* `id`
* `purchase_id`
* `scheduled_delivery_at`
* `delivered_at`
* `return_status`
* `carrier`
* `tracking_number`
* `return_barcode_generated`
* `return_label_created_at`
* `accepted_by_carrier_at`
* `return_requested_at`
* `return_authorized_at`
* `return_received_at`
* `return_rejected_at`
* `return_rejection_reason`
* `refund_window_expires_at`
* `created_at`
* `updated_at`

Rules:

* `return_status` is `not_requested`, `requested`, `authorized`, `accepted_by_carrier`, `received`, `rejected`, or `cancelled`.
* Rejected returns require rejection timestamp and reason.
* Delivery timing is enforced by a trigger because it compares detail timestamps to `purchases.purchased_at`.
* Trigger derives the 30-day refund window.

Policy use:

* Preparation requests the return and creates simulated barcode/label state.
* Fund issuance requires carrier acceptance.
* Rejected or cancelled return status blocks workflow.

### `subscription_purchase_details`

Purpose: Subscription billing period, cancellation, renewal, and proration facts.

Columns:

* `id`
* `purchase_id`
* `period_start`
* `period_end`
* `cancelled_at`
* `service_ended_at`
* `auto_renew`
* `refund_proration_mode`
* `full_refund_window_expires_at`
* `refund_window_expires_at`
* `created_at`
* `updated_at`

Rules:

* `period_end > period_start`.
* `auto_renew` defaults to `true`.
* `refund_proration_mode` is `none`, `full`, or `prorated`.
* Trigger derives full-refund and refund-window deadlines.
* Trigger disables auto-renew and sets service end when cancellation is present.

Policy use:

* Refund handling requires an active billing period.
* Full refund applies inside 48 hours.
* Prorated refund uses unused time in the current active billing period.
* Preparation cancels service access and records the refund mode.

## Model Audit Layer

Migration `014_create_model_audit_tables.py` adds the Phase 1 audit foundation.

| Table | Purpose |
| --- | --- |
| `model_audit_sessions` | Parent record for one model-backed chat request, including `trace_id`, customer/request identifiers, model name, status, token counts, and latency. |
| `model_audit_events` | Ordered per-session timeline keyed by `(session_id, sequence_number)`, with optional workflow, tool, summary, input, output, and metadata JSON. |
| `model_audit_event_lookup` | Normalized event-key catalog for admin UI labels, categories, ordering, descriptions, and active-state control. |

Rules:

* Session status is `running`, `succeeded`, or `failed`.
* Event rows reference `model_audit_event_lookup.event_key`.
* Lookup categories are `request`, `routing`, `tool`, `validation`, `mutation`, `response`, or `error`.
* Backend code writes through `repositories/audit.py` and `services/audit.py`.
* `/api/chat` creates a session for each valid request, persists ordered graph trace events, and completes or fails the session with token and latency metrics.
* Migration `015_broadcast_model_audit_events.py` adds an after-insert trigger on `model_audit_events` that publishes event payloads through PostgreSQL `pg_notify`.

## Database-Managed Refund Fields

Migration `010_add_refund_deadline_triggers.py` creates trigger functions:

`set_digital_purchase_refund_fields` derives:

* `refund_window_expires_at = purchased_at + 15 days`
* `code_delivered_at = purchased_at + 5 minutes` when missing
* redeemed-code lock reason

`set_physical_purchase_refund_fields` derives:

* `refund_window_expires_at = purchased_at + 30 days`

`set_subscription_purchase_refund_fields` derives:

* `full_refund_window_expires_at = purchased_at + 48 hours`
* `refund_window_expires_at = period_end`
* cancellation defaults

Clients, model prompts, and service commands must not provide authoritative deadline values.

## Guarded Mutation Expectations

Repository writes use expected SQL state and require exactly one affected row.

Examples:

* Digital refund preparation checks completed digital purchase, unredeemed code, and no invalidation timestamp.
* Physical refund preparation checks completed physical purchase and untouched return state.
* Subscription refund preparation checks active subscription state with no cancellation or proration mode.
* Issuance checks `purchases.status = 'refund_pending'`.
* Carrier acceptance checks requested physical return and no prior acceptance timestamp.
* Refund confirmation persistence checks purchase ownership, purchase type, and detail-row target.
* Refund confirmation consumption checks the same customer, purchase, expected command,
  granted/matched state, and unused consumption fields.

If any expected state check fails, the transaction rolls back through
`RepositoryConflictError`.

## Seed Data

Identity seed:

* 15 customer users.
* 1 administrator user.
* 2 roles: `customer`, `admin`.
* 16 role assignments.

Product seed:

* 14 physical products.
* 10 digital products.
* 6 subscription products.

Purchase seed:

* 180 deterministic purchases across 15 customers.
* 12 purchases per customer.
* Distribution: 90 physical, 54 digital, 36 subscription.
* Purchase dates generally span `2026-05-20` through `2026-07-03`.
* Digital purchases are constrained to `2026-06-20` through `2026-07-04`.

Detail seed:

* One matching detail row per purchase.
* 54 digital detail rows.
* 90 physical detail rows.
* 36 subscription detail rows.

Seed validators confirm:

* Counts match by type.
* Each purchase has exactly one matching detail row.
* Digital issued codes are unique.
* Redeemed digital codes include redemption timestamps.
* Physical delivery timestamps obey delivery-window rules.
* Subscription periods are ordered correctly.

## Query Patterns

Customer purchase history reads join `purchases` to `products`, filter by
`purchases.user_id`, and order by `purchases.purchased_at desc`.

Purchase detail reads:

1. Load `purchases.id` and `purchases.purchase_type`.
2. Read exactly one detail table based on `purchase_type`.
3. Return a stable API shape with `purchase_id`, `purchase_type`, and `details`.

Refund workflow reads:

1. Load purchase facts needed by policy.
2. Load matching detail row.
3. Evaluate deterministic policy in `services/refund_policy.py`.
4. Return serialized workflow decision.

Model audit admin reads:

1. Read `model_audit_sessions` in reverse `started_at` order for the session list.
2. Join `model_audit_events` to count events for session summaries.
3. Join `model_audit_events` to `model_audit_event_lookup` for event labels, categories, descriptions, and display order.
4. Order event timelines by `sequence_number`.

Model audit stream reads:

1. Listen on the `model_audit_events` PostgreSQL notification channel.
2. Relay notifications through `/api/admin/audit/events/stream` as SSE frames.
3. Optionally filter relayed notifications by `session_id`.

## Migration List

| Migration | Purpose |
| --- | --- |
| `000_schema_foundation` | `schema_migrations` and required PostgreSQL extensions. |
| `001_create_users` | Identity anchor table. |
| `002_create_roles` | Role definitions. |
| `003_create_user_roles` | User-role assignments. |
| `004_create_products` | Consolidated product catalog. |
| `005_create_purchases` | Customer purchase history. |
| `006_create_digital_purchase_details` | Digital detail extension table. |
| `007_create_physical_purchase_details` | Physical detail extension table and delivery-window trigger. |
| `008_create_subscription_purchase_details` | Subscription detail extension table. |
| `009_expand_purchase_details_for_refund_state` | Refund lifecycle fields on detail tables. |
| `010_add_refund_deadline_triggers` | Database-managed refund deadlines/defaults. |
| `011_add_refund_workflow_state` | `refund_pending` status and physical label/barcode fields. |
| `012_add_refund_issued_facts` | Purchase-level refund request and issued refund facts. |
| `013_add_refund_confirmation_state` | Detail-level refund confirmation authorization and consumption facts. |
| `014_create_model_audit_tables` | Model audit session, event timeline, and event lookup tables for v0.6.0. |
| `015_broadcast_model_audit_events` | PostgreSQL notification trigger for realtime model audit event streams. |

## Migration Commands

From `apps/api`:

```bash
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator status
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator apply
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator seed
```

Migration modules expose:

* `MIGRATION_ID`
* `DESCRIPTION`
* `upgrade(connection)`

Most table-creation migrations also split `create_table`, `create_indexes`, `enable_rls`,
and `create_policies`.

## Schema Change Standard

When schema changes:

* Add or update ordered migrations.
* Update seed logic if required.
* Update API contracts for exposed fields.
* Update business logic documentation for changed rules.
* Update tests for migrations, repositories, services, and frontend mapping where applicable.

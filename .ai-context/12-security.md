# 12-security.md

# Security Boundaries

## Purpose

This document defines the security boundaries of the application, including implemented protections, intentionally mocked functionality, and production considerations.

---

# Security Principles

* Backend services are the authoritative security boundary.
* The frontend is never trusted as a source of truth.
* Sensitive operations require backend validation.
* Business policy is enforced server-side.
* API keys and secrets remain server-side at all times.
* Refund state is authoritative database state and cannot be overridden by clients or AI-generated reasoning.

---

# Mocked Security

The following functionality is intentionally mocked for the purposes of this project:

* Customer authentication
* Administrator authentication
* Customer identity verification
* Financial transactions
* Payment processing

These implementations exist to demonstrate application flow rather than production security.

---

# Production Security

In a production environment, the following would be implemented:

* Secure authentication
* Role-based authorization
* Customer identity verification
* Session management
* Rate limiting
* Audit logging
* Secure payment processing

These features remain outside the scope of this technical challenge.

---

# Environment Variables

* Secrets must be stored in environment variables.
* API keys must never be committed to source control.
* Secrets must never be exposed to the frontend.
* Environment files should remain local and be excluded from version control.
* `SUPABASE_DB_URL` is backend-only and must not be exposed to frontend code.

---

# AI Security

* The language model may access backend tools only.
* The language model never communicates directly with the database.
* Tool access is validated by backend services.
* The language model may not bypass deterministic business logic or policy enforcement.
* AI refund tools expose backend-evaluated information rather than trusting model reasoning.

---

# Data Access

Customer access:

* View only customer-owned information.

Administrator access:

* Customer-specific information requires customer verification.
* Administrative access should remain scoped to the active customer session.

Backend services determine what data may be returned for every request.

Refund decisions occur only inside backend policy services. Clients may request workflow actions, but they cannot provide authoritative eligibility, lifecycle status, refund outcome, refund amount, or refund deadline values.

---

# Database Security

The backend remains the only application layer permitted to connect to Supabase PostgreSQL.

Business-data tables should enable PostgreSQL row-level security when introduced. RLS policies should be defined in the same migration that creates the protected table so intended access boundaries are documented and applied with the schema.

The internal `schema_migrations` table is migration metadata and does not require business-data RLS policies.

The `users` table enables row-level security when created. Its initial policy grants access only to Supabase `service_role`, preserving the backend-only database access boundary while authentication remains mocked.

The `roles` table enables row-level security when created. Its initial policy grants access only to Supabase `service_role`, preserving backend ownership of role definitions.

The `user_roles` table enables row-level security when created. Its initial policy grants access only to Supabase `service_role`, preserving backend ownership of role assignment state.

Identity-layer roles determine which mocked interface a user enters. They do not represent production authentication, a permissions matrix, feature flags, or authorization logic.

The `products` table enables row-level security when created. Its initial policy grants access only to Supabase `service_role`, preserving backend ownership of catalog reference data.

The `purchases` table enables row-level security when created. Its initial policy grants access only to Supabase `service_role`, preserving backend ownership of customer purchase history and preventing direct frontend access.

The purchase detail tables enable row-level security when created. Their initial policies grant access only to Supabase `service_role`, preserving backend ownership of type-specific purchase state.

Refund lifecycle state is stored inside purchase detail tables. The backend service role is the only application path allowed to read or mutate this state. No standalone `refunds` table should be introduced, and no frontend Supabase client should be allowed to write refund eligibility or lifecycle fields.

Refund deadline fields are database-managed through PostgreSQL triggers. Clients and AI tools must not provide authoritative deadline values.

Refund preparation and issuance are separate backend-controlled operations. Fund issuance must not skip the type-specific preparation step, even when preparation is immediate for digital or subscription purchases.

Refund workflow mutations are strict commands. Repository writes guard expected database state and raise conflicts when duplicate calls, stale reads, or partial lifecycle state prevent exactly one row from being updated. Routes expose those conflicts as endpoint-specific `409` responses instead of silently returning current state or rewriting timestamps.

Issued mock refunds persist `refunded_at`, `refund_amount_cents`, and `refund_outcome` on `purchases`. Backend policy reads those persisted facts for already-refunded purchases so the system cannot forget or recompute issued credit after the status changes to `refunded`.

---

# Frontend Trust Boundary

The frontend is responsible for presentation only.

Authoritative information should always be retrieved through backend APIs.

Frontend state should never be trusted for:

* Customer identity
* Refund eligibility
* Refund lifecycle state
* Business policy
* Financial state
* Administrative permissions

---

# Repository Security

* Never commit secrets or API keys.
* Keep local configuration files out of source control.
* Validate sensitive changes before merging.
* Document security-related architectural changes within `.ai-context/` as they are introduced.

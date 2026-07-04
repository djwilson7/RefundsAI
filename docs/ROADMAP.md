# Roadmap

This roadmap defines the planned implementation sequence for RefundsAI. Each milestone establishes a stable foundation for the next, allowing the project to evolve incrementally while maintaining architectural integrity, testing quality, and documentation throughout development.

---

# v0.0.0 — Project Foundation

**Status:** Complete

## Objective

Establish the architectural and engineering foundation before implementation begins.

### Deliverables

* [x] Repository initialized.
* [x] AI agent bootstrap process established.
* [x] `.ai-context` documentation completed.
* [x] Initial README created.
* [x] Initial project structure defined.

### Validation

* [x] Repository successfully initialized.
* [x] Documentation committed.
* [x] Initial GitHub repository established.

---

# v0.1.0 — Development Foundation

**Status:** Complete

## Objective

Establish a reproducible local development foundation and validate that the frontend, backend, database, testing, linting, build, and documentation workflows are functional before application features are implemented.

This milestone proves the project can be developed safely and consistently.

### Deliverables

#### Repository

* [x] Scaffold frontend application.
* [x] Scaffold backend application.
* [x] Establish frontend project directory structure.
* [x] Establish backend project directory structure.
* [x] Configure backend dependency management.
* [x] Configure frontend local development workflow.

#### Frontend

* [x] Next.js
* [x] TypeScript
* [x] Tailwind CSS
* [x] CSS Modules
* [x] Local development server
* [x] Lint configuration
* [x] Testing framework
* [x] Production build configuration

#### Backend

* [x] FastAPI
* [x] Python
* [x] Dependency management
* [x] Health endpoint
* [x] Lint configuration
* [x] Testing framework
* [x] Coverage reporting

#### Database

* [x] Add Supabase environment configuration scaffolding.
* [x] Add backend database health endpoint.
* [x] Configure Supabase development project credentials.
* [x] Validate live Supabase database connectivity.

#### Development Environment

* [x] Frontend Dockerfile
* [x] Backend Dockerfile
* [x] Docker Compose frontend service
* [x] Docker Compose backend service
* [x] Complete Docker Compose development environment
* [x] Frontend local-first development workflow
* [x] Backend local-first development workflow

#### Documentation

* [x] Frontend local setup instructions
* [x] Backend local setup instructions
* [x] Backend dependency configuration
* [x] Frontend development commands
* [x] Backend development commands
* [x] Frontend testing commands
* [x] Backend testing commands
* [x] Frontend Docker workflow
* [x] Backend Docker workflow

### Validation

Successfully verify:

* [x] Frontend starts locally.
* [x] Backend starts locally.
* [x] Backend health endpoint responds successfully.
* [x] Backend communicates with Supabase.
* [x] Environment variables load correctly.
* [x] Docker Compose starts the complete development environment.
* [x] Docker Compose starts the frontend service.
* [x] Docker Compose starts the backend service.
* [x] Frontend lint passes.
* [x] Backend lint passes.
* [x] Frontend tests pass.
* [x] Backend tests pass.
* [x] Frontend production build succeeds.
* [x] Backend coverage executes successfully.
* [x] Documentation accurately reflects the frontend local development workflow.

### Out of Scope

* Authentication
* Database schema
* Seed data
* Business API endpoints
* OpenAI integration
* Agent orchestration
* Customer interface
* Admin interface
* Voice functionality
* Refund workflows

---

# v0.2.0 — Database Schema Integration

**Status:** Complete

## Objective

Build the database schema, migration flow, seed data, and database-owned lifecycle state needed by future backend services, frontend experiences, and AI orchestration.

This milestone is focused on durable data structures and realistic mock data. Backend business services and API contracts are intentionally deferred to v0.3.0. LangGraph orchestration is deferred to v0.5.0.

### Planned Deliverables

* [x] Backend-owned database migration runner
* [x] Complete database schema
* [x] Complete migration set
* [x] Complete seed data set
* [x] Refund management architecture

#### Database Foundation Progress

* [x] Create `schema_migrations` migration metadata table.
* [x] Create `users` identity anchor table.
* [x] Create `roles` role definition table.
* [x] Create `user_roles` role assignment table.
* [x] Configure row-level security on identity business tables.
* [x] Configure backend-only `service_role` policies for identity tables.
* [x] Deploy identity migrations to Supabase.
* [x] Define `products` catalog migration.
* [x] Define `purchases` purchase history migration.
* [x] Define product-type-specific purchase detail migrations.
* [x] Deploy products and purchases migrations to Supabase.
* [x] Deploy purchase detail migrations to Supabase.
* [x] Expand purchase detail tables with embedded refund lifecycle fields and database-managed deadline triggers.
* [x] Confirm v0.2.0 schema scope is complete before backend service work begins.

#### Seed Data Progress

* [x] Add deterministic identity mock data under `apps/api/mockdata`.
* [x] Seed 15 customer users.
* [x] Seed 1 administrator user.
* [x] Seed `customer` and `admin` roles.
* [x] Seed 16 user-role assignments.
* [x] Verify seeded Supabase row counts and role distribution.
* [x] Add deterministic product and purchase mock data under `apps/api/mockdata`.
* [x] Define 30 catalog products across physical, digital, and subscription types.
* [x] Generate 180 customer purchases across the seeded customer users.
* [x] Define deterministic purchase detail seed generation for digital, physical, and subscription lifecycle state.
* [x] Seed purchase detail lifecycle rows for digital, physical, and subscription purchases.
* [x] Update seed data to rely on database-managed refund lifecycle defaults and deadlines.
* [x] Confirm v0.2.0 seed scope is complete before backend service work begins.

#### Refund Management Progress

* [x] Decide that refund state is owned by purchase detail tables.
* [x] Deploy refund lifecycle fields to purchase detail tables.
* [x] Deploy database triggers for refund deadline and derived field calculation.
* [x] Prepare schema for backend refund policy services.
* [x] Prepare schema for future refund API endpoints.
* [x] Prepare schema for future AI refund tools.

### Validation

* [x] Complete database schema successfully deployed.
* [x] Complete seed data generated.
* [x] Backend lint passing.
* [x] Backend tests passing.
* [x] Coverage maintained above project targets.
* [x] Database-backed refund state validated.

---

# v0.3.0 — Backend Business Logic Foundation

**Status:** Complete

## Objective

Build the backend service layer on top of the v0.2.0 database schema.

This milestone is primarily focused on making business logic sound, testable, and accessible through clear API contracts. The frontend does not need to be connected yet, but the backend should expose stable endpoints and response models that the frontend can call in v0.4.0.

The backend services should read from the concrete tables introduced in v0.2.0, including `users`, `roles`, `user_roles`, `products`, `purchases`, `digital_purchase_details`, `physical_purchase_details`, and `subscription_purchase_details`.

This milestone also prepares deterministic services for later AI orchestration. LangGraph nodes and AI tools should call backend services rather than reaching into database logic directly.

### Planned Deliverables

* [x] Repository pattern
* [x] Business service layer
* [x] API contracts
* [x] Shared request and response models
* [x] Identity and role lookup services over `users`, `roles`, and `user_roles`
* [x] Purchase history services over `purchases`
* [x] Purchase detail services over `digital_purchase_details`, `physical_purchase_details`, and `subscription_purchase_details`
* [x] Refund policy evaluation services
* [x] Refund API endpoints that expose evaluated eligibility and execute approved workflows
* [x] Backend tests for repositories, services, policy, API, and migration boundaries

#### Frontend Read Path Progress

* [x] Add repository-backed read path for selectable mock users.
* [x] Add `GET /api/users/mock`.
* [x] Add `GET /api/users/{user_id}` with role information.
* [x] Add `GET /api/users/{user_id}/purchases` with product metadata and `details_url`.
* [x] Add `GET /api/purchases/{purchase_id}/details`.
* [x] Resolve purchase detail tables internally from `purchases.purchase_type`.
* [x] Keep frontend contract independent of digital, physical, and subscription detail table names.
* [x] Document the first frontend read-path API contracts in `.ai-context/09-api.md`.
* [x] Add backend unit tests for the first frontend read-path API contracts and detail-table resolution.

#### Refund Eligibility Progress

* [x] Add deterministic refund policy helper functions for physical, digital, and subscription purchases.
* [x] Add read-only `GET /api/purchases/{purchase_id}/refund/eligibility`.
* [x] Evaluate refund eligibility from `purchases` plus the matching purchase detail table.
* [x] Distinguish workflow entry, preparation, and fund issuance decisions.
* [x] Support full and prorated subscription eligibility calculations.
* [x] Add backend unit tests that cross-check refund rules against `docs/REFUND_POLICY.md`.
* [x] Refactor refund decisions into eligibility, preparation, and issuance stages.
* [x] Add physical return preparation schema fields for simulated barcode and label creation.
* [x] Add refund request, refund issue, digital code redemption, and carrier acceptance endpoints.
* [x] Add backend tests for workflow guards, preparation, issuance gates, mutation endpoints, and migration SQL.
* [x] Persist issued refund facts on `purchases` and read them for already-refunded workflow responses.
* [x] Add strict duplicate/stale mutation handling with repository conflict errors and endpoint-specific `409` responses.
* [x] Rename the mutating application service from `ApplicationReadService` to `ApplicationService`.

### Validation

* [x] API contracts implemented for the frontend read path and refund workflow endpoints.
* [x] Repository and service layers validated.
* [x] Backend services return frontend-ready response shapes.
* [x] Refund eligibility and lifecycle transitions covered by tests.
* [x] Backend lint, build, tests, and coverage passing.

---

# v0.4.0 — Customer Experience

## Objective

Build the customer-facing experience on top of the backend API contracts from v0.3.0.

### Planned Deliverables

* [x] Customer dashboard baseline
* [x] Purchase history
* [x] Purchase detail pages
* [ ] Refund eligibility views
* [ ] Refund request experience
* [ ] Navigation
* [x] Shared UI components
* [ ] Persistent support panel

#### Customer Experience Progress

* [x] Add mock authentication flow with customer/admin entry points.
* [x] Add customer home route backed by selected user profile and purchase history data.
* [x] Add purchase history cards that navigate to purchase details.
* [x] Add API-backed purchase detail route using `GET /api/purchases/{purchase_id}/details`.
* [x] Add type-specific purchase detail sections for digital, physical, and subscription purchases.
* [x] Add subscription billing-cycle display and renewal/cancellation badge in the subscription detail header.
* [x] Keep purchase detail metadata focused on refund workflow facts after moving product-type lifecycle facts into dedicated sections.

### Validation

* [x] Customer interface navigable through mock login, customer home, purchase history, and purchase details.
* [x] Purchase information displayed from backend read APIs.
* [ ] Refund state rendered accurately.
* [x] Frontend tests, lint, and build passing for current customer detail scope.

---

# v0.5.0 — AI Orchestration

## Objective

Implement the AI orchestration layer responsible for customer interactions and deterministic workflow execution, using the backend services established in v0.3.0.

### Planned Deliverables

* [ ] OpenAI integration
* [ ] Tool/function calling
* [ ] Customer and admin data access boundaries needed by AI tools
* [ ] Tool contracts for refund eligibility lookup and policy-approved refund execution
* [ ] Conversation management
* [ ] LangGraph node definitions for backend tool orchestration
* [ ] LangGraph workflow assembly
* [ ] Refund workflow orchestration
* [ ] Policy-aware decision flow
* [ ] Audit event generation
* [ ] Reasoning trace support
* [ ] Backend tests for graph-node boundaries

### Validation

* [ ] Agent successfully completes eligible refunds.
* [ ] Agent correctly denies policy violations.
* [ ] Tool execution validated.
* [ ] LangGraph nodes can call backend services through stable contracts.
* [ ] AI reasoning captured through audit logs.

---

# v0.6.0 — Administrative Experience

## Objective

Provide administrators with operational visibility into customer interactions and AI behavior.

### Planned Deliverables

* [ ] Admin dashboard
* [ ] Customer verification workflow
* [ ] Customer lookup
* [ ] AI execution trace viewer
* [ ] Operational metrics
* [ ] Support session timeline
* [ ] Administrative AI assistance

### Validation

* [ ] Customer verification workflow functional.
* [ ] AI traces visible.
* [ ] Customer history accessible after verification.
* [ ] Administrative workflows validated.

---

# v0.7.0 — Voice Support

## Objective

Extend the existing AI orchestration pipeline to support voice interactions.

### Planned Deliverables

* [ ] Speech transcription
* [ ] Shared text and voice orchestration
* [ ] Voice conversation support
* [ ] Transcript storage
* [ ] Voice audit events

### Validation

* [ ] Voice requests follow the same orchestration pipeline as text.
* [ ] Transcripts stored successfully.
* [ ] Voice interactions appear within audit history.

---

# v0.8.0 — Deferred Implementation Points

## Objective

Track useful but non-core implementation points that are intentionally deferred unless time allows. These items may improve production realism, polish, or platform completeness, but they are not required for the primary technical challenge path.

### Planned Deliverables

* [ ] Standalone products API boundary over `products`.
* [ ] Product catalog service/tool access beyond purchase-history metadata.
* [ ] Full mobile optimization pass.
* [ ] Production authentication for customers and administrators.
* [ ] Role-based authorization and permissions matrix.
* [ ] Session management and identity verification hardening.
* [ ] Rate limiting and abuse protection.
* [ ] Production payment processor integration.
* [ ] Hosted deployment and public demo environment.
* [ ] Production-scale catalog modeling for inventory, entitlements, and subscription metadata.
* [ ] Stronger database-level enforcement for cross-table purchase-detail exclusivity.

### Validation

* [ ] Deferred items remain documented and explicitly scoped outside the core challenge path.
* [ ] Any promoted deferred item receives matching `.ai-context` updates, tests, and API documentation.

---

# v1.0.0 — Technical Challenge Submission

## Objective

Prepare RefundsAI for final presentation and evaluation.

### Planned Deliverables

* [ ] Feature-complete implementation
* [ ] Final documentation review
* [ ] README completion
* [ ] Comprehensive testing pass
* [ ] Repository cleanup
* [ ] Loom walkthrough
* [ ] Public GitHub repository

### Validation

* [ ] Repository builds successfully.
* [ ] Test suite passes.
* [ ] Coverage maintained above project targets.
* [ ] README complete.
* [ ] Loom walkthrough recorded.
* [ ] Repository ready for reviewer evaluation.

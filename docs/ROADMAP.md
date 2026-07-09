# Roadmap

This roadmap defines the planned implementation sequence for RefundsAI.

Each milestone establishes a stable foundation for the next. The goal is incremental
delivery without losing architecture, test quality, or documentation alignment.

The core implementation through v0.6.0 is complete. v1.0.0 tracks final submission
work only; deferred production features remain intentionally out of scope.

---

# v0.0.0 - Project Foundation

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

# v0.1.0 - Development Foundation

**Status:** Complete

## Objective

Establish a reproducible local development foundation.

The milestone validates that frontend, backend, database connectivity, testing, linting,
build, and documentation workflows are functional before feature work begins.

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

# v0.2.0 - Database Schema Integration

**Status:** Complete

## Objective

Build the database schema, migration flow, seed data, and database-owned lifecycle state needed by future backend services, frontend experiences, and AI orchestration.

This milestone is focused on durable data structures and realistic mock data.

Backend business services and API contracts are intentionally deferred to v0.3.0.
LangGraph orchestration is deferred to v0.5.0.

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

# v0.3.0 - Backend Business Logic Foundation

**Status:** Complete

## Objective

Build the backend service layer on top of the v0.2.0 database schema.

This milestone is primarily focused on making business logic sound, testable, and
accessible through clear API contracts.

The frontend does not need to be connected yet, but the backend should expose stable
endpoints and response models that the frontend can call in v0.4.0.

Backend services should read from the concrete tables introduced in v0.2.0:

* `users`
* `roles`
* `user_roles`
* `products`
* `purchases`
* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

This milestone also prepares deterministic services for later AI orchestration.
LangGraph nodes and AI tools should call backend services rather than reaching into
database logic directly.

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

# v0.4.0 - Customer Experience

**Status:** Complete

## Objective

Build the customer-facing experience on top of the backend API contracts from v0.3.0.

### Planned Deliverables

* [x] Customer dashboard baseline
* [x] Purchase history
* [x] Purchase detail pages
* [x] Refund eligibility views
* [x] Manual refund workflow command experience
* [x] Navigation
* [x] Shared UI components
* [x] Persistent support panel shell

#### Customer Experience Progress

* [x] Add mock authentication flow with customer/admin entry points.
* [x] Add customer home route backed by selected user profile and purchase history data.
* [x] Add purchase history cards that navigate to purchase details.
* [x] Add client-facing navigation across mock login, customer home, purchase history, purchase details, and logout.
* [x] Add API-backed purchase detail route using `GET /api/purchases/{purchase_id}/details`.
* [x] Add type-specific purchase detail sections for digital, physical, and subscription purchases.
* [x] Add subscription billing-cycle display and cancellation/refund summary rows under subscription detail sections.
* [x] Keep purchase detail metadata focused on refund workflow facts after moving product-type lifecycle facts into dedicated sections.
* [x] Add persistent help-panel command surface that can manually trigger backend refund preparation and issuance while AI orchestration is pending.
* [x] Add rich prepared and issued refund displays for digital code invalidation,
  physical return preparation/carrier acceptance, and subscription cancellation/refund
  summary state.
* [x] Document that the manual `Prep Refund` and `Issue Refund` commands are temporary and should be removed or demoted once the agent owns refund workflow execution.

### Validation

* [x] Customer interface navigable through mock login, customer home, purchase history, and purchase details.
* [x] Purchase information displayed from backend read APIs.
* [x] Refund state rendered accurately for prepared and issued digital, physical, and subscription workflows.
* [x] Frontend tests, lint, and build passing for current customer detail scope.

---

# v0.5.0 - AI Agent Integration

**Status:** Complete

## Objective

Implement the AI agent layer incrementally and complete the technical exercise scope
through purchase intelligence, deterministic refund policy lookup, backend-evaluated
refund eligibility, and confirmation-gated refund workflow execution.

The agent uses `gpt-5.4-mini` for the current OpenAI integration.

The completed milestone proves the model can retrieve account facts, call deterministic
tools, preserve compact conversation context, explain backend-owned refund policy,
communicate backend-evaluated eligibility, and execute confirmed backend-approved
refund workflow actions without making the model the business authority.

### Planned Deliverables

#### Phase 1: Read-Only Purchase Intelligence

* [x] OpenAI and LangGraph foundation for conversational question understanding.
* [x] Read-only customer purchase-history tools backed by existing backend services.
* [x] Agent responses for purchase-history summaries, counts, totals, and type-based aggregation.
* [x] Structured execution logs for intent classification, tool calls, computed aggregates, and final responses.
* [x] Backend tests for read-only graph-node boundaries and purchase-summary behavior.
* [x] Focused graph-node modules for validation, tool selection, tool execution, and final response generation.
* [x] Active result-set response grounding for scoped follow-up list and ranked-selection questions.

#### Phase 2: Policy Lookup

Example customer question: "What is the refund policy for my digital products?"

* [x] Read-only refund policy lookup tools backed by deterministic backend policy sources.
* [x] Product-type-aware policy explanation flow for digital, physical, and subscription purchases.
* [x] Agent responses for policy windows, policy requirements, exclusions, and next-step guidance without evaluating a specific purchase as refundable.
* [x] Structured logs for policy lookup, product-type scope, policy source selection, and final policy response.
* [x] Backend tests confirming the agent does not invent or override refund policy.
* [x] Compact conversation state for selected purchase type, selected product, selected purchase id, selected policy scope, and selected date range.
* [x] Selected purchase set precedence for pronoun and latest-item follow-ups before global most-recent fallback.
* [x] Compact current-page context for all-purchases and purchase-detail chat grounding without sending full page content.
* [x] Fail-closed product entity resolution before product-specific policy lookup.
* [x] Product-name resolver for policy follow-ups using exact, partial, and fuzzy matching against backend purchase rows.
* [x] Explicit product-name follow-ups can escape narrowed selected sets and re-resolve against full purchase history.
* [x] Object-operation workflow lookup for policy follow-ups, including demonstrative references to the active result set.

#### Phase 3: Eligibility Evaluation

Example customer question: "Which of my digital products can be refunded?"

* [x] Read-only refund workflow tools backed by deterministic backend eligibility services.
* [x] Eligibility explanation flow that communicates backend-evaluated purchase outcomes without mutating refund state.
* [x] Agent responses for refundable purchases, refund denials, eligibility reasons, required next actions, and policy context.
* [x] Structured logs for eligibility tool selection, deterministic eligibility results, policy context, and non-mutating refund guidance.
* [x] Backend tests confirming the agent does not infer, override, or calculate refund eligibility outside deterministic backend services.
* [x] Structured readable trace formatting for workflow classification, workflow context, execution decisions, tool results, and final-response model context.

#### Phase 4: Refund Workflow

Example customer question: "Start a refund for the eligible one."

* [x] Confirmation-gated mutating refund workflow actions for policy-approved preparation and issuance.
* [x] Explicit user-confirmation gate before any agent-triggered refund mutation.
* [x] LangGraph workflow for preparing refunds, continuing approved in-progress refund steps, and reporting final state.
* [x] Structured logs for confirmation requests, mutation attempts, workflow conflicts, and outcomes.
* [x] Backend tests confirming mutations require explicit confirmation and still rely on deterministic backend services.

### Validation

* [x] Agent accurately answers read-only purchase-history questions from backend data.
* [x] Agent correctly explains refund policy without evaluating account-specific eligibility.
* [x] Agent resolves phase-two policy follow-ups from compact conversation state without replaying the full transcript.
* [x] Agent resolves purchase-detail page policy follow-ups from current page purchase id without evaluating eligibility.
* [x] Agent resolves active-result-set policy and eligibility follow-ups without treating demonstrative phrases as literal product names.
* [x] Agent correctly explains backend-evaluated refund eligibility without mutating refund workflow state.
* [x] Agent creates pending refund actions before mutation and executes refund preparation or issuance only after direct confirmation.
* [x] LangGraph nodes call backend services through stable contracts.
* [x] Structured logs capture intent, workflow lookup, tool execution, aggregate
  calculations, policy lookup, eligibility lookup, active-result-set previews,
  confirmation gates, mutation outcomes, and final responses.

---

# v0.6.0 - Administrative Experience

**Status:** Complete

## Objective

Provide administrators with operational visibility, AI auditability, and live monitoring of customer interactions and agent behavior. The focus is on auditing the AI's reasoning rather than general customer administration.

### Planned Deliverables

#### Phase 1: Audit Model Foundation

* [x] Add `model_audit_sessions` as the parent request/session record.
* [x] Add `model_audit_events` as the ordered per-session event timeline.
* [x] Add `model_audit_event_lookup` as the normalized event-key mapping for UI labels, categories, ordering, descriptions, and active-state control.
* [x] Add backend audit writer service.
* [x] Validate lint, build, test, and strictly above-90% coverage before applying the migration.
* [x] Apply the migration after validation passes.
* [x] Update `docs/` and `.ai-context/` with concise implementation-grounded audit model documentation.

#### Phase 2: Graph Instrumentation

* [x] Create an audit session at chat request start.
* [x] Persist each graph/log step as an audit event.
* [x] Capture workflow, context, tools, validation, mutation, response, and errors.
* [x] Store token usage and latency on the audit session.

#### Phase 3: Read APIs

* [x] Add `GET /api/admin/audit/sessions`.
* [x] Add `GET /api/admin/audit/sessions/:id`.
* [x] Add `GET /api/admin/audit/sessions/:id/events`.

#### Phase 4: Realtime Stream

* [x] Add an SSE endpoint for active audit events.
* [x] Support streaming by `session_id` or all active sessions.
* [x] Broadcast audit events from the database when event rows are inserted.
* [x] Stream events to the Admin UI as graph execution progresses.

#### Phase 5: Admin UI

* [x] Add audit session list.
* [x] Add session detail timeline.
* [x] Add expandable raw event payloads.
* [x] Separate request identity, process performance, and token metrics.
* [x] Add tool-purpose descriptions and a complete narrative event timeline.

### Validation

* [x] Graph execution events successfully persisted as structured audit events.
* [x] Backend SSE stream exposes database-broadcast audit events.
* [x] Live timeline replayed in the Admin UI without page refreshes.
* [x] Historical sessions accessible through backend read APIs with token usage and latency fields.
* [x] Admin UI preserves every event and maps trace types to audience-readable labels.

---

# v0.7.0 - Deferred Implementation Points

## Objective

Track useful but non-core implementation points that are intentionally deferred unless
scope changes.

These items may improve production realism, polish, or platform completeness, but they
are not required for the primary technical challenge path. The current project state is
complete enough for final review once documentation, validation, and walkthrough polish
are finished.

### Planned Deliverables

#### Voice Agent Support

* [ ] Speech transcription.
* [ ] Shared text and voice orchestration.
* [ ] Voice conversation support.
* [ ] Transcript storage.
* [ ] Voice audit events.
* [ ] Voice requests follow the same orchestration pipeline as text.
* [ ] Voice interactions appear within audit history.

#### Production and Platform Hardening

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

# v1.0.0 - Technical Challenge Submission

## Objective

Prepare the current RefundsAI implementation for final presentation and evaluation.
This milestone should not add new product surfaces unless a blocking issue is found.

### Planned Deliverables

* [x] Feature-complete core implementation through text chat, refund workflow execution, and admin auditability.
* [x] Final `.ai-context` review
* [x] README and supporting-document completion
* [x] Comprehensive testing pass
* [ ] Repository cleanup
* [ ] Loom walkthrough
* [ ] Public GitHub repository

### Validation

* [x] Repository builds successfully.
* [x] Test suite passes.
* [x] Coverage maintained above project targets.
* [x] README complete.
* [ ] Loom walkthrough recorded.
* [x] Repository ready for reviewer evaluation.

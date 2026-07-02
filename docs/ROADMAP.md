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

**Status:** In Progress

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

* [ ] Configure Supabase development project.
* [ ] Establish backend database connection.
* [ ] Validate database connectivity.
* [ ] Verify environment configuration.

#### Development Environment

* [x] Frontend Dockerfile
* [x] Backend Dockerfile
* [x] Docker Compose frontend service
* [x] Docker Compose backend service
* [ ] Complete Docker Compose development environment
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
* [ ] Backend communicates with Supabase.
* [ ] Environment variables load correctly.
* [ ] Docker Compose starts the complete development environment.
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

# v0.2.0 — Backend Foundation

## Objective

Build the backend foundation that supports deterministic business logic, database operations, and future AI orchestration.

### Planned Deliverables

* [ ] Database schema
* [ ] Initial migrations
* [ ] Seed data generation
* [ ] Repository pattern
* [ ] Business service layer
* [ ] API contracts
* [ ] Shared models
* [ ] Configuration layer

### Validation

* [ ] Database schema successfully deployed.
* [ ] Seed data generated.
* [ ] API contracts implemented.
* [ ] Backend tests passing.
* [ ] Coverage maintained above project targets.

---

# v0.3.0 — Customer Experience

## Objective

Build the customer-facing experience independent of AI functionality.

### Planned Deliverables

* [ ] Customer dashboard
* [ ] Purchase history
* [ ] Purchase detail pages
* [ ] Refund eligibility views
* [ ] Navigation
* [ ] Shared UI components
* [ ] Persistent support panel

### Validation

* [ ] Customer interface fully navigable.
* [ ] Purchase information displayed correctly.
* [ ] Refund state rendered accurately.
* [ ] Frontend tests and build passing.

---

# v0.4.0 — AI Orchestration

## Objective

Implement the AI orchestration layer responsible for customer interactions and deterministic workflow execution.

### Planned Deliverables

* [ ] OpenAI integration
* [ ] Tool/function calling
* [ ] Conversation management
* [ ] Refund workflow orchestration
* [ ] Policy-aware decision flow
* [ ] Audit event generation
* [ ] Reasoning trace support

### Validation

* [ ] Agent successfully completes eligible refunds.
* [ ] Agent correctly denies policy violations.
* [ ] Tool execution validated.
* [ ] AI reasoning captured through audit logs.

---

# v0.5.0 — Administrative Experience

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

# v0.6.0 — Voice Support

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

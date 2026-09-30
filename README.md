# RefundsAI

> A bounded AI agent that explains and executes refunds against strict backend policy.

RefundsAI is a production-inspired customer support system for end-to-end refund
workflows. The model interprets customer language, requests narrow read tools, and
explains backend results. Deterministic services remain authoritative for policy,
consent, refund amounts, and lifecycle transitions.

Exact confirmation turns can bypass the model entirely. The backend validates persisted
consent, executes guarded refund operations, verifies the database result, and returns
transactional wording without another provider call.

The core implementation is complete through text chat, confirmation-gated refund
execution, and administrative auditability.

---

## Project Goals

RefundsAI demonstrates:

* **Bounded Agentic Interface**: Natural-language understanding and grounded tool orchestration.
* **Deterministic Enforcement**: Backend policy rules decide eligibility, not LLM inference.
* **Safe Execution**: Exact, persisted, once-consumable confirmation gates protect mutations.
* **Observability & Auditability**: Ordered model, tool, validation, and mutation evidence.
* **Layered System Boundaries**: Clean separation between model, services, and database.

---

## Features

### Customer Portal

* Mock customer login (stored in local session storage)
* Customer dashboard and purchase history overview
* Type-specific purchase detail pages (Digital, Physical, Subscription)
* AI support panel with conversational history and active result grounding
* Chat-driven refund workflow controls with backend confirmation gates

### Admin Dashboard (AI Auditability)

* Mock administrator login
* **Audit Session Overview**: Chronological list of customer-agent chat sessions
* **Audit Session Details**: Request identity, process metrics, token usage, tool history, and complete narrative timeline
* **Realtime Audit Stream**: SSE-backed refresh from persisted PostgreSQL events

---

## Architecture

RefundsAI separates conversational orchestration from transaction authority.

```text
Customer / Administrator
        |
        v
  Next.js Web UI
        |
        v
 FastAPI + LangGraph
    /           \
   v             v
OpenAI read/   Deterministic routing,
explanation   policy, consent, mutations
    \           /
     v         v
   Backend services
          |
          v
 Supabase PostgreSQL
```

### Business Policy & Authority

* **Authoritative Policy**: Backend service helpers compute eligibility from real database facts. The AI model only reports eligibility and collects confirmations.
* **Lifecycle State Separation**: Refund states are recorded directly in type-specific detail tables. The shared `purchases` table tracks shared order details and final refund facts.
* **No Standalone `refunds` Table**: Lifecycle and confirmation facts belong directly to:
  * `digital_purchase_details`
  * `physical_purchase_details`
  * `subscription_purchase_details`
* **Gated Mutations**: Mutations require persisted, validated, once-consumable confirmation facts, preventing the model from authorizing writes.
* **Database Triggers**: PostgreSQL triggers derive refund deadlines and defaults automatically from persisted purchase/detail state.

### End-to-End Refund Proof

1. The customer asks about policy or a purchase.
2. The backend resolves the customer, purchase scope, and workflow.
3. Read-only tools return policy or eligibility facts.
4. The assistant presents the exact product-specific confirmation command.
5. The backend persists consent and executes guarded preparation or issuance.
6. The purchase view refreshes from database state.
7. The admin audit surface shows every model and deterministic step.

---

## Technology Stack

#### Frontend

* Next.js (app router)
* React & TypeScript
* Tailwind CSS
* Framer Motion

#### Backend

* FastAPI (endpoint serving)
* Python (v3.12+)
* Pydantic v2 (data schemas and input validation)
* psycopg (PostgreSQL database driver)
* pytest & pytest-cov (testing and coverage verification)
* Ruff (linting and formatting)

#### Database

* Supabase PostgreSQL (relational database storage)
* Triggers & PL/pgSQL functions (database-level policy/deadline enforcement)

#### AI

* LangGraph (graph-based conversational state and agent orchestration)
* OpenAI APIs (structured completions and function calling)

Voice-agent support is deferred and is not part of the current implemented surface.

#### Development

* Docker & Docker Compose
* GitHub / Git Version Control

---

## Local Development

This project is intentionally scoped for local-first development.

Production deployment is not the primary objective of this technical challenge.

### Frontend

The frontend scaffold lives in `apps/web` and is managed through the root npm workspace.

Install frontend dependencies from the repository root:

```bash
npm install
cd apps/web
```

Run the frontend:

```bash
npm run dev
```

Lint:

```bash
npm run lint
```

Test:

```bash
npm run test
```

Coverage:

```bash
npm run coverage
```

Build:

```bash
npm run build
```

The same commands are also exposed from the repository root as `npm run web:dev`, `npm run web:lint`, `npm run web:test`, `npm run web:coverage`, and `npm run web:build`.

The local development server runs on `http://localhost:3000`.

The frontend server reads `REFUNDS_AI_API_BASE_URL` when calling the FastAPI backend from server-rendered routes. For local development this defaults to `http://localhost:8000`.

#### Frontend-only Docker development

Use the dedicated development Compose file when working on the product landing page or
other frontend-only changes:

```bash
docker compose -f docker-compose.dev.yml up --build
```

This configuration starts only the Next.js development server. It bind-mounts
`apps/web`, keeps the generated `.next` output in a Docker volume, and enables polling
with Next.js webpack development mode so edits and atomic file replacements made on
Windows trigger hot reload without rebuilding the image. The FastAPI and database
services do not start. Local development outside Docker continues to use Next.js's
default development bundler.

The development container reads `REFUNDS_AI_DEMO_MODE` when it is created:

* Unset or `true`: show the product landing page at `/`.
* `false`: show the original mock authentication screen at `/`.

Source edits hot reload immediately. After changing `.env`, recreate the container so
Docker injects the updated process environment:

```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate
```

Set `REFUNDS_AI_WEB_PORT` when port 3000 is already occupied, for example
`REFUNDS_AI_WEB_PORT=3010`.

#### Root experience

The frontend root route (`/`) shows the public RefundsAI product landing page by
default. Set `REFUNDS_AI_DEMO_MODE=false` to restore the original mock authentication
entry screen for integrated application walkthroughs. The product landing page is
presentational and makes no external service calls.

#### Mock frontend authentication

`Load User` selects a random seeded customer identity, builds mock credentials in the format `first_last@example.com` with password `12345Password`, animates those read-only credentials into the form, stores the selected mock customer in browser session storage, and routes to `/user-home?customerId={customerId}`. The `customerId` query parameter is used by `/user-home` to request the selected user through `GET /api/users/{user_id}` so the header name and customer metadata come from the backend API. If the backend is unavailable during frontend-only development, the screen falls back to the selected seeded identity.

`Load Admin` follows the same credential animation flow for the seeded administrator identity and routes to `/admin-home`.

This mock login state is frontend-only. It does not authenticate against the FastAPI backend, does not grant production permissions, and does not make the frontend authoritative for customer, purchase, refund, or policy data.

### Frontend Container

```bash
docker compose up web --build
```

The standard Compose configuration builds the production-style standalone frontend
and starts its API dependency. Use `docker-compose.dev.yml` for frontend-only hot
reload. The container exposes the frontend on `http://localhost:3000`.

### Backend

The backend scaffold lives in `apps/api` and uses FastAPI with pinned pip requirements.

Create the virtual environment from the repository root:

```bash
python --version
python -m venv apps/api/.venv
cd apps/api
```

Activate the virtual environment for your shell:

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1
```

```cmd
:: Command Prompt
.venv\Scripts\activate.bat
```

```bash
# Git Bash / WSL / macOS / Linux
source .venv/bin/activate
```

Install backend dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the API:

```bash
python -m uvicorn refunds_ai_api.main:app --app-dir src --reload
```

Lint:

```bash
python -m ruff check src tests
```

Test:

```bash
python -m pytest tests
```

Coverage:

```bash
python -m pytest tests --cov=refunds_ai_api --cov-report=term-missing --cov-fail-under=90
```

Build check:

```bash
python -m compileall src tests
```

Backend direct dependencies are pinned in `apps/api/requirements.txt` and `apps/api/requirements-dev.txt`. The resolved validation baseline is recorded in `apps/api/requirements.lock`.

The local API server runs on `http://localhost:8000`.

Uvicorn logs may show `http://0.0.0.0:8000` from inside Docker. Use `http://localhost:8000` from the host machine.

### Backend Container

```bash
docker compose up api --build
```

The container exposes the backend on `http://localhost:8000`.

FastAPI docs are available at `http://localhost:8000/docs`.

### Supabase Database

Create a Supabase project, then copy the PostgreSQL connection string from Project Settings > Database.

For local API development, you can configure `SUPABASE_DB_URL` in the repository root `.env` file (the application automatically searches parent directories up to `../../.env` as a fallback) or create `apps/api/.env` locally:

```bash
cd apps/api
cp .env.example .env
```

Set `SUPABASE_DB_URL` to the Supabase PostgreSQL connection string.

For Docker Compose, create a root `.env` from the tracked example:

```bash
cp .env.example .env
```

Docker Compose passes `SUPABASE_DB_URL` and `DATABASE_CONNECT_TIMEOUT_SECONDS` into the API container.

Check database connectivity:

```bash
curl http://localhost:8000/health/database
```

The database health check endpoint returns HTTP `200 OK` on success, or `503 Service Unavailable` when database configuration is missing or connectivity checks fail. It validates connectivity only; use the migration commands for schema readiness.

Apply migrations and seed demo data from `apps/api`:

```bash
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator apply
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator seed
```

For a destructive clean demo reset, apply migrations and reseed from today's UTC date:

```bash
$env:REFUNDSAI_ALLOW_DEMO_DB_RESET = "true"
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator reset-demo
```

`reset-demo` clears seeded users, roles, products, purchases, purchase details, audit sessions, and audit events before reseeding. It is development/demo-only and is blocked unless the explicit reset flag is set.

### AI Chat Configuration

The AI chat flow uses OpenAI and LangGraph for purchase intelligence, policy lookup, backend-evaluated refund eligibility, and confirmation-gated refund workflow actions.

Set the backend AI environment variables in `apps/api/.env` for local API development, or in the repository root `.env` for Docker Compose:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

Check model connectivity:

```bash
curl http://localhost:8000/health/model
```

### AI Chat Orchestration Details

The customer support panel communicates with the backend via `POST /api/chat`. The orchestration logic operates through several distinct phases:

#### 1. Context & Pronoun Resolution
To resolve references like *"those purchases"* or *"this item"* without replaying the full chat transcript, requests carry a compact `conversation_state` and `page_context`:
* **Page Grounding**: Resolves the customer's active purchase-detail page ID or category view.
* **Context Resolution Priority**: Matches references against (1) page context, (2) active refund workflow state, (3) explicit product/SKU/order names, (4) active result sets, and (5) global history.
* **Result Set Scopes**: Stores a `scope_label` (e.g., list/aggregate results) so that ordinal descriptors (*"last one"*, *"oldest"*, *"cheapest"*) evaluate within the active query results.

#### 2. Read-Only Backend Tools
The LangGraph workflow resolves and executes deterministic tools on behalf of the customer:
* `validate_customer_account`: Read the active mock customer.
* `get_customer_purchase_history`: Fetch all customer purchases.
* `get_purchase_history_by_date_range`: Search purchases within a date window.
* `get_purchase_count_by_amount_threshold`: Count purchases above/below a price.
* `get_refund_policy`: Retrieve deterministic policy rules.
* `get_refund_eligibility`: Evaluate backend-computed eligibility facts.

#### 3. Confirmation-Gated Mutations
The model never holds the consent authority to mutate database state. Mutations are protected by exact matching commands:
* **Digital Purchase**: Requires `Confirm invalidate code and issue refund`
* **Subscription Purchase**: Requires `Confirm cancel and issue refund`
* **Physical Purchase**: Requires `Confirm start return and issue label`

* **Safety Guards**: Ambiguous confirmations (*"yes"*, *"do it"*, *"proceed"*) are rejected at the mutation boundary; only the exact canonical command grants authorization.
* **Atomic Transitions**: Digital and subscription validations may trigger preparation and issuance back-to-back, but the backend processes them as distinct database transactions. Physical workflows halt at return preparation until carrier acceptance is logged.
* **Selective Model Use**: Canonical confirmation turns can execute and respond deterministically with zero model calls.

---

## Repository Structure

```text
.
|-- .ai-context/
|-- apps/
|   |-- api/
|   `-- web/
|-- docs/
|-- AGENTS.md
|-- docker-compose.yml
`-- README.md
```

---

## Project Context

RefundsAI follows a documentation-first development workflow.

The `.ai-context/` directory contains the authoritative project documentation, including:

* Project vision
* Architecture
* System boundaries
* Business logic
* Engineering standards
* Testing expectations
* API contracts
* Database design
* Tool specifications
* Security boundaries

Both human contributors and AI engineering agents should reference this documentation before making implementation decisions.

Supporting project documents:

* [`docs/REFUND_POLICY.md`](docs/REFUND_POLICY.md)
* [`docs/DEVELOPER_INSIGHTS.md`](docs/DEVELOPER_INSIGHTS.md)
* [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## License

This repository is provided as part of a technical demonstration and portfolio project.

RefundsAI is source-available for technical evaluation and reference only. The
code is not open source and may not be used, copied, modified, redistributed,
hosted, or commercialized without prior written permission.

See [`LICENSE`](LICENSE) for the full terms.

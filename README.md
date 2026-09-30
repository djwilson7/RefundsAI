# RefundsAI

> AI-assisted refunds. Backend-owned policy. Visible execution.

Built as a seven-day technical delivery, RefundsAI combines conversational support
with deterministic policy, explicit consent, guarded execution, and auditability.

The frontend showcases how that infrastructure can fit into a customer experience.
The repository contains the backend workflow that gives it substance.

## Product Walkthrough

Explore the customer experience and the evidence behind it.
[Run locally](#local-development), then choose **Technical tour → Client or Admin → Begin Here**.

### Landing page

The product introduction establishes the central rule: the model interprets and explains;
backend services decide what is allowed.

![RefundsAI product landing page](docs/images/landing.jpg)

### Choose a perspective

Client shows support in purchase context. Admin shows performance and execution evidence.
Both use example identities, with swap and exit controls in the shared header.

![Client and Admin walkthrough entry](docs/images/perspectives.jpg)

### Client: purchase history and support

The support panel sits beside purchase history, illustrating an integration within an
existing customer portal. Purchase context stays visible throughout the conversation.

![Client purchase history with the support panel open](docs/images/client-history.jpg)

### Client: purchase details

Status, lifecycle events, and refund policy provide the facts the support workflow needs.
Digital, physical, and subscription purchases each have their own requirements.

![Purchase details and refund policy alongside the support panel](docs/images/purchase-details.jpg)

### Admin: performance overview

Review successes, failures, total tokens, and average events, tool calls, latency,
and time to response across example sessions.

![Admin overview with aggregate metrics and example audit history](docs/images/admin-overview.jpg)

### Admin: execution evidence

Follow a request through its response, tool outcomes, and ordered events.
Expand inspection sections for identity, token breakdowns, and payloads.

![Admin session with prompt, response, tools, and execution evidence](docs/images/admin-session.jpg)

<details>
<summary>Additional support and mobile views</summary>

![Support preview within the client experience](docs/images/client-support.jpg)

The client experience adapts to mobile, with full-screen support when opened.

<img src="docs/images/client-mobile.jpg" alt="Mobile client dashboard with compact header actions and purchase history" width="390" />

</details>

**Walkthrough boundary:** these screens use local examples. Support is a fixed preview
with a disabled composer; no external services or refund actions run in the walkthrough.

## Seven-Day Core Delivery

The backend implementation supplies the workflow illustrated above.

| Capability | Responsibility |
| --- | --- |
| Language and context | Resolve intent, purchase references, and active workflow scope. |
| Grounded tools | Read purchase facts, policy, and evaluated eligibility. |
| Policy enforcement | Determine eligibility from persisted facts. |
| Confirmation gates | Validate exact, scoped, once-consumable consent. |
| Guarded execution | Apply permitted lifecycle transitions and verify persistence. |
| Auditability | Record model, tool, validation, and mutation evidence. |

Exact confirmation turns can execute entirely in the backend, without another model call.
Real authentication, payment processing, and production hardening are outside this scope.

## Architecture

The API separates the presentation surface from the core workflow.
Next.js is one example integration; another customer-facing interface can use the same boundary.

```text
Customer interface / Admin interface
                 |
          FastAPI + LangGraph
             /         \
      Model             Deterministic services
      Interpret         Policy + consent
      Request reads     Guarded execution
      Explain           Verify outcomes
             \         /
          Supabase PostgreSQL
```

| Layer | Owns |
| --- | --- |
| Frontend | Customer context, interaction, and presentation. |
| Model | Language interpretation, read-tool requests, and grounded explanations. |
| Backend | Policy decisions, consent validation, and refund execution. |
| Database | Authoritative facts, lifecycle state, and ordered audit records. |

Refund state lives with its product type: `digital_purchase_details`,
`physical_purchase_details`, or `subscription_purchase_details`.
The shared `purchases` table holds order and final refund summary facts.

[Refund policy](docs/REFUND_POLICY.md) · [Engineering reasoning](docs/DEVELOPER_INSIGHTS.md) ·
[Architecture reference](.ai-context/01-architecture.md)

## Explore or Integrate

| Mode | Behavior |
| --- | --- |
| Default walkthrough | Local examples; no API, database, or model credentials required. |
| Integrated build | Live backend reads, conversational support, guarded refunds, persisted audits, and SSE updates. |

Set `REFUNDS_AI_DEMO_MODE=false` before building or starting development to use the
integrated application. Its mock login supplies example identities, not production authentication.

[Service isolation](#frontend-demo-isolation) documents the enforced walkthrough boundary.
Dates in generated examples follow the current UTC day; screenshots were captured September 30, 2026.

## Technology Stack

| Surface | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS, Framer Motion |
| API and orchestration | FastAPI, Python, Pydantic, LangGraph, OpenAI |
| Persistence | Supabase PostgreSQL, psycopg, PL/pgSQL |
| Validation | Vitest, ESLint, pytest, pytest-cov, Ruff |
| Development | npm workspaces, Docker Compose, Git |

---

## Local Development

This project is intentionally scoped for local-first development.

Production deployment is not the primary objective of this technical challenge.

### Frontend

The frontend lives in `apps/web` and is managed through the root npm workspace.
Its default demo needs only the frontend dependencies. Backend, database, and AI
setup below applies to integrated development.

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

#### Browser extension hydration warnings

`apps/web/src/app/layout.tsx` uses `suppressHydrationWarning` on `<html>` and
`<body>` to tolerate attributes injected before hydration by browser extensions,
such as Grammarly's `data-new-gr-c-s-check-loaded` and `data-gr-ext-installed`.
This prevents document-shell attribute warnings from interrupting the demo while
keeping hydration checks enabled inside the application.

This tolerance does not prevent extensions from changing page content. If an
extension changes nested elements or breaks interactions, disable it for the demo
site or use a browser profile with extensions disabled, then reload and inspect
any remaining mismatch.

Only integrated builds (`REFUNDS_AI_DEMO_MODE=false`) use
`REFUNDS_AI_API_BASE_URL` for FastAPI calls (default `http://localhost:8000`).

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

* Unset or `true`: frontend-only demo, with generated data and no service calls.
* `false`: integrated application and original mock authentication screen at `/`.

Source edits hot reload immediately. After changing `.env`, recreate the container so
Docker injects the updated process environment:

```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate
```

Set `REFUNDS_AI_WEB_PORT` when port 3000 is already occupied, for example
`REFUNDS_AI_WEB_PORT=3010`.

#### Demo routes and data

* Client examples use local seed snapshots, with dates anchored to the current UTC day at 14:00.
* Admin examples contain six stable sessions, without live pagination, SSE, or persistence.
* Aggregates include failures and deterministic confirmations; missing timings are excluded.
* Zero provider tokens and estimated backend payload tokens remain distinct.
* Inspection sections start collapsed in walkthrough routes and open in integrated live routes.

#### Frontend demo isolation

* **Build boundary:** `REFUNDS_AI_DEMO_MODE` is selected at build/development startup. Rebuild to change production mode.
* **Route safety:** query parameters cannot unlock services. Unknown example IDs return not found.
* **Service guards:** `src/lib/demo-mode.ts` blocks readers, chat, mutations, and subscriptions. Proxies return `404 DEMO_SERVICE_DISABLED` before processing requests.
* **Browser boundary:** the CSP permits connections and assets only from the application's own origin.
* **Local data:** `apps/web/src/lib/fixtures` owns the examples; no backend files or credentials are required.
* **Containers:** development Compose runs only the frontend; standard Compose supports integrated development.

| Validation | Command |
| --- | --- |
| Service isolation | `npm run test:demo --workspace @refunds-ai/web` |
| Integrated expectations, with mocked services | `npm run test:integrated --workspace @refunds-ai/web` |
| Both test projects | `npm run web:test` |

Isolation tests reject attempted fetch/SSE connections and cover direct URLs, proxies,
accidental live-component mounts, and the disabled support composer.

#### Integrated mock frontend authentication

This login flow applies only to integrated builds. Walkthrough entry uses a fixed example identity.

* `Load User` selects a seeded customer, displays mock credentials, and stores the identity in session storage.
* `/user-home?customerId={customerId}` loads profile data through the backend, with a seeded identity fallback.
* `Load Admin` uses the seeded administrator and opens `/admin-home`.

Mock identity selection does not authenticate with FastAPI or grant production permissions.
Backend facts remain authoritative for purchases, policy, and refunds.

### Frontend Container

```bash
docker compose up web --build
```

The standard Compose configuration builds the production-style standalone frontend
and starts its API dependency. Use `docker-compose.dev.yml` for frontend-only hot
reload. The container exposes the frontend on `http://localhost:3000`.

### Backend

The integrated backend lives in `apps/api` and uses FastAPI with pinned pip requirements.

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

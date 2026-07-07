# RefundsAI

> Policy-governed AI customer support for modern refund workflows.

RefundsAI is a production-inspired AI customer support platform that demonstrates how Large Language Models can automate customer support workflows while preserving deterministic business logic, transparent policy enforcement, and operational auditability.

Rather than allowing the language model to independently make business decisions, RefundsAI uses AI as the conversational interface between users and business systems. The model gathers context, orchestrates backend tools, communicates outcomes, and escalates interactions when policy or customer behavior requires human intervention. Deterministic backend services remain the authoritative source for all operational decisions.

---

## Project Goals

RefundsAI demonstrates:

* AI-powered customer support through natural language.
* Deterministic policy enforcement.
* Tool-based AI orchestration.
* Transparent AI reasoning and auditability.
* Production-inspired system architecture.
* Clean separation between AI and business logic.

---

## Features

### Customer Portal

* Mock customer login
* Account overview
* Purchase history
* Purchase details
* Refund eligibility
* AI support through text and voice
* Support conversation history

### Admin Dashboard

* Mock administrator login
* Customer verification workflow
* Operational metrics
* Customer purchase history
* AI execution trace
* Support session timeline
* Conversational administrative insights

---

## Architecture

RefundsAI follows a layered architecture that separates user experience from business authority.

```text
Customer / Administrator
            │
            ▼
     Next.js Frontend
            │
            ▼
      FastAPI Backend
            │
            ▼
     OpenAI Model Layer
            │
            ▼
     Backend Tool Layer
            │
            ▼
Deterministic Business Services
            │
            ▼
   Supabase PostgreSQL
```

Business policy remains authoritative.

The language model orchestrates workflows rather than making business decisions.

Refund eligibility is computed from persisted database state. The shared `purchases` table records purchase history, while each purchase type owns its own refund-blocking and refund-lifecycle facts in its detail table:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

The project intentionally does not use a standalone `refunds` table. Backend policy services load the purchase and its matching detail record, evaluate the policy, and persist any lifecycle updates back to the owning detail table. PostgreSQL triggers compute refund deadlines and derivable defaults from persisted purchase/detail state. AI tools expose backend-evaluated information rather than asking the model to infer eligibility from incomplete context.

---

## Technology Stack

### Frontend

* Next.js
* TypeScript
* Tailwind CSS
* Framer Motion

### Backend

* FastAPI
* Python

### Database

* Supabase PostgreSQL

### AI

* OpenAI APIs
* Function Calling
* Voice Transcription

### Development

* Docker
* Docker Compose
* GitHub

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

#### Mock frontend authentication

The frontend root route (`/`) is a mock authentication landing page for local UI development.

`Load User` selects a random seeded customer identity, builds mock credentials in the format `first_last@example.com` with password `12345Password`, animates those read-only credentials into the form, stores the selected mock customer in browser session storage, and routes to `/user-home?customerId={customerId}`. The `customerId` query parameter is used by `/user-home` to request the selected user through `GET /api/users/{user_id}` so the header name and customer metadata come from the backend API. If the backend is unavailable during frontend-only development, the screen falls back to the selected seeded identity.

`Load Admin` follows the same credential animation flow for the seeded administrator identity and routes to `/admin-home`.

This mock login state is frontend-only. It does not authenticate against the FastAPI backend, does not grant production permissions, and does not make the frontend authoritative for customer, purchase, refund, or policy data.

### Frontend Container

```bash
docker compose up web --build
```

The container exposes the frontend on `http://localhost:3000`.

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

The database health check endpoint returns HTTP `200 OK` on success, or `503 Service Unavailable` when database configuration is missing or connectivity checks fail. It validates connectivity only; schema, migrations, seed data, and business tables remain part of the next milestone.

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

The shared frontend help panel sends text messages through the same-origin frontend proxy to `POST /api/chat`. The backend runs read-only account tools for purchase-history, amount-threshold, date-range, refund-policy, and refund-eligibility questions, logs the observable orchestration steps to the backend console, and returns plain-text assistant responses. Chat requests include compact page context for the all-purchases surface or the active purchase-detail id. Chat responses include compact conversation state for selected purchase type, selected product, selected purchase id, selected purchase ids, selected scope label, selected policy scope, selected date range, selected refund purchase ids, selected refund context, active refund context, active result set, active workflow, pending refund action, and the backend-resolved current page reference so policy, eligibility, and workflow follow-ups can resolve references like "those purchases" or "this item" without replaying the full transcript or sending full page content. After a single-purchase eligibility result, active refund context records the evaluated purchase, next workflow action, and canonical confirmation command. Refund preparation and issuance are deterministic backend actions, not model-callable write tools: digital purchases require `Confirm invalidate code and issue refund`, subscriptions require `Confirm cancel and issue refund`, and physical purchases require `Confirm start return and issue label`. Generic replies such as "yes", "proceed", "do it", or "continue" do not mutate refund state after the command boundary has been issued; only the expected canonical command creates the internal `pending_refund_action` and enters the existing backend `request_refund` or `issue_refund` validation path. The graph resolves deterministic context before honoring model-requested tools: page purchase references, active refund workflow context, explicit product/SKU/order/purchase-id references, selected single purchase, scoped selected purchase set, global purchase history, then clarification. Aggregate/list results become the active scope for ranked follow-ups and store a customer-facing scope label, so phrases like "last one", "oldest", "cheapest", and "most expensive" resolve inside the selected purchase set before falling back to global purchase history. Ranking-only follow-ups remain account-fact questions and do not call refund policy or eligibility tools unless the user explicitly asks about policy, cancellation rules, refundability, eligibility, approval, or refund process. Explicit named product references such as "Developer Toolkit" escape any narrowed selected set, resolve against the full active purchase history, and use the matched purchase's actual purchase type for policy or eligibility lookup. Named product references must resolve to an actual purchase before product-specific policy or eligibility lookup; unresolved or ambiguous products get a clarification instead of inferred policy or eligibility. The assistant may explain backend-evaluated eligibility outcomes and execute confirmed backend-approved refund preparation or issuance, but voice capture and persisted AI trace history remain future phases.

---

## Repository Structure

```text
.
├── .ai-context/
├── apps/
│   ├── api/
│   └── web/
├── AGENTS.md
├── docker-compose.yml
└── README.md
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

---

## License

This repository is provided as part of a technical demonstration and portfolio project.

License information will be added prior to public release.

# RefundsAI API

FastAPI backend for RefundsAI's customer, purchase, refund workflow, and Phase 1 read-only AI chat surfaces.

## Local Setup

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

Use `requirements.txt` and `requirements-dev.txt` for direct dependency management. `requirements.lock` records the resolved baseline used for scaffold validation.

## Run

```bash
python -m uvicorn refunds_ai_api.main:app --app-dir src --reload
```

The local API server runs on `http://localhost:8000`.

Uvicorn logs may show `http://0.0.0.0:8000` from inside Docker. Use `http://localhost:8000` from the host machine.

## Supabase

For local development, you can configure `SUPABASE_DB_URL` in the repository root `.env` file (the application automatically searches parent directories up to `../../.env` as a fallback) or create a local environment file:

```bash
cp .env.example .env
```

Set `SUPABASE_DB_URL` to the Supabase PostgreSQL connection string from Project Settings > Database.

Check database connectivity:

```bash
curl http://localhost:8000/health/database
```

This endpoint returns HTTP `200 OK` on success, or `503 Service Unavailable` when database configuration is missing or connectivity fails. It validates the PostgreSQL handshake only; schema readiness is handled by the migration commands below.

## AI Chat

Configure the OpenAI model used by the LangGraph chat flow:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

Check model connectivity:

```bash
curl http://localhost:8000/health/model
```

The support panel sends user messages to `POST /api/chat`. The orchestration logic operates through several distinct phases:

### 1. Context & Pronoun Resolution
Requests carry a compact `conversation_state` and `page_context`:
* **Page Grounding**: Resolves the customer's active purchase-detail page or category view.
* **Context Resolution Priority**: Matches references against (1) page context, (2) active refund workflow state, (3) explicit product/SKU/order names, (4) active result sets, and (5) global history.
* **Result Set Scopes**: Stores a `scope_label` (e.g., list/aggregate results) so that ordinal descriptors (*"last one"*, *"oldest"*, *"cheapest"*) evaluate within the active query results.

### 2. Read-Only Backend Tools
The LangGraph workflow resolves and executes deterministic tools on behalf of the customer:
* `get_customer_purchase_history`: Fetch all customer purchases.
* `get_purchase_history_by_date_range`: Search purchases within a date window.
* `get_purchase_count_by_amount_threshold`: Count purchases above/below a price.
* `get_refund_policy`: Retrieve deterministic policy rules.
* `get_refund_eligibility`: Evaluate backend-computed eligibility facts.

### 3. Confirmation-Gated Mutations
The model never holds the consent authority to mutate database state. Mutations are protected by exact matching commands:
* **Digital Purchase**: Requires `Confirm invalidate code and issue refund`
* **Subscription Purchase**: Requires `Confirm cancel and issue refund`
* **Physical Purchase**: Requires `Confirm start return and issue label`

* **Safety Guards**: Ambiguous confirmations (*"yes"*, *"do it"*, *"proceed"*) are rejected at the mutation boundary; only the exact canonical command grants authorization.
* **Atomic Transitions**: Digital and subscription validations may trigger preparation and issuance back-to-back, but the backend processes them as distinct database transactions. Physical workflows halt at return preparation until carrier acceptance is logged.

### 4. Trace Events
The backend emits sequential trace events for model requests, tool selection, tool execution, tool results, blocked responses, and final assistant responses. Real-time tracing and session persistence are captured for administrative audit.

## Database Migrations

Run schema migrations from this directory:

```bash
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator apply
```

Inspect migration state:

```bash
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator status
```

Run idempotent seed data steps:

```bash
$env:PYTHONPATH = "src"; python -m refunds_ai_api.database.migrator seed
```

Migration modules live in `src/refunds_ai_api/database/migrations/`. Seed steps live in `src/refunds_ai_api/database/seeds.py`.

Mock data fixtures live in `mockdata/`. The identity fixture is `mockdata/identity_seed.json`; the product and purchase fixture is `mockdata/purchase_seed.json`.

### Schema & Lifecycle Strategy
* **State Isolation**: Refund lifecycle and confirmation states reside within purchase-specific detail tables (e.g. `digital_purchase_details`), not a standalone `refunds` table.
* **Deterministic Policy**: Backend service helpers calculate eligibility from database facts. The AI model only queries this policy via read-only tools.
* **Database Triggers**: PostgreSQL triggers handle automatic refund window deadlines (15 days for digital, 30 days for physical, active period for subscription) and defaults, keeping service code simple and client inputs non-authoritative.

## Lint

```bash
python -m ruff check src tests
```

## Test

```bash
python -m pytest tests
```

## Coverage

```bash
python -m pytest tests --cov=refunds_ai_api --cov-report=term-missing --cov-fail-under=90
```

## Build Check

```bash
python -m compileall src tests
```

## Container

Run the container from the repository root:

```bash
docker compose up api --build
```

The container exposes the API on `http://localhost:8000`.

FastAPI docs are available at `http://localhost:8000/docs`.

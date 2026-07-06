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

Configure the OpenAI model used by the read-only LangGraph chat flow:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

Check model connectivity:

```bash
curl http://localhost:8000/health/model
```

The `POST /api/chat` endpoint runs read-only tools for purchase-history, amount-threshold, date-range, and refund-policy questions. Requests include compact page context for the all-purchases surface or the active purchase-detail id. Responses include compact conversation state for selected purchase type, selected product, selected purchase id, selected purchase ids, selected policy scope, selected date range, and backend-resolved current page reference so the next request can resolve policy follow-ups without sending the full transcript or full page content. Scoped follow-ups such as "latest one" resolve inside the selected purchase set before falling back to the global most recent purchase. Explicit named product references such as "Developer Toolkit" escape any narrowed selected set, resolve against the full active purchase history, and use the matched purchase's actual purchase type for policy lookup. Named product references must resolve to an actual purchase before product-specific policy lookup; unresolved products get a clarification instead of inferred policy. The backend emits sequential console-visible trace events for model requests, tool selection, tool execution, tool results, blocked responses, and final assistant responses. The chat graph does not evaluate account-specific refund eligibility, capture voice input, persist conversation logs, or mutate refund state.

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

Refund lifecycle state is stored in the purchase detail tables, not in a standalone `refunds` table. Backend policy services should load `purchases` plus the matching detail table, evaluate eligibility, and persist approved lifecycle changes back to that detail table. Database triggers compute refund deadline fields and derivable defaults, so service code should send event facts rather than client-computed deadline values.

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

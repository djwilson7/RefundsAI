# RefundsAI API

FastAPI backend scaffold for the RefundsAI development foundation milestone.

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

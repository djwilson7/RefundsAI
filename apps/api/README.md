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

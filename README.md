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

AI service setup instructions will be added as those milestones are scaffolded.

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

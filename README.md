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

```bash
npm install
npm run web:dev
npm run web:lint
npm run web:test
npm run web:coverage
npm run web:build
```

The local development server runs on `http://localhost:3000`.

### Frontend Container

```bash
docker compose up web --build
```

The container exposes the frontend on `http://localhost:3000`.

Backend, database, and AI service setup instructions will be added as those milestones are scaffolded.

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

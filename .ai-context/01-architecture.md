# 01-architecture.md

# System Architecture

## Overview

The platform follows a layered architecture that separates presentation, backend services, AI orchestration, business logic, and persistent storage into independent layers.

Each layer has a single responsibility and communicates only through well-defined interfaces.

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

---

## Frontend

**Technology**

* Next.js
* TypeScript
* Tailwind CSS

**Primary Interfaces**

* Customer Portal
* Admin Operations Dashboard
* Persistent Chat Interface
* Voice Interface

---

## Backend

**Technology**

* FastAPI
* Python

**Primary Responsibilities**

* API endpoints
* Session management
* AI request orchestration
* Tool execution
* Business service coordination
* Audit logging

---

## Database

**Technology**

* Supabase PostgreSQL

**Primary Data**

* Customers
* Purchases
* Refunds
* Policies
* Support Sessions
* AI Events
* Voice Transcripts

---

## Model Layer

**Technology**

* OpenAI APIs
* Function Calling
* Voice Transcription

**Purpose**

* Intent recognition
* Context gathering
* Response generation
* Backend tool orchestration
* Customer and administrator communication

---

## Tool Layer

The model interacts with backend functionality exclusively through structured tools.

Tool categories include:

* Customer
* Purchases
* Refunds
* Policies
* Support History
* Administration
* Audit

---

## Voice Flow

Voice interactions follow the same architecture as text conversations.

```text
Voice Input
      │
      ▼
Speech Transcription
      │
      ▼
Model Orchestration
      │
      ▼
Backend Tools
      │
      ▼
Business Services
      │
      ▼
Response
```

---

## High-Level Request Flow

Every interaction follows the same system path.

```text
User
→ Frontend
→ Backend
→ Model
→ Tool Calls
→ Business Services
→ Database
→ Business Services
→ Model Response
→ Frontend
```

The architecture intentionally separates user interaction, AI orchestration, business operations, and persistent data into independent layers to maintain modularity, auditability, and clear system ownership.

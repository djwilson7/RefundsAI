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

**Current Frontend Routes**

* `/` renders the mock authentication landing page.
* `/user-home` renders the customer home screen from a `customerId` query parameter.
* `/admin-home` renders the administrator home placeholder.
* `/purchase-details/[purchaseId]` renders a server-loaded purchase detail page from `GET /api/purchases/{purchase_id}/details`.

The mock landing page derives local-only credentials from seeded identities, animates those credentials into read-only form fields, and then navigates to the appropriate home route. Customer home rendering uses the route query parameter rather than browser-only state so server-rendered and hydrated output match on refresh.

Purchase detail rendering uses one stable route and one stable backend detail endpoint. The frontend passes purchase summary data from the purchase history card for header continuity, then loads the authoritative purchase detail payload from the API. The detail page renders product-type-specific sections:

* Digital purchases show purchase/code issuance steps and issued-code redemption state.
* Physical purchases show delivery steps and delivery tracking data.
* Subscription purchases show billing-cycle progress and a header renewal badge.

Subscription renewal state is displayed in the purchase detail header. Active renewal shows `Auto Renew Enabled`; disabled renewal or cancellation/service-end state shows `Subscription Canceled`. The badge is derived from backend detail state and does not make the frontend authoritative for cancellation or refund policy.

The customer purchase summary page and purchase detail pages expose a fixed bottom-right help trigger. The root application shell owns the persistent help layer so the panel state can survive navigation between those purchase surfaces. Opening the trigger shifts the main application content left, slides in a full-height right-side help panel, and moves the trigger with the content edge. The trigger shows a chat icon when closed and a collapse-panel icon when open. Help content remains placeholder text until the persistent support panel and AI support workflow are implemented.

The help panel is a command surface, not the refund state display. On the purchase summary route it instructs the user to select a purchase from purchase history. On purchase detail routes it reads backend refund workflow eligibility and presents `Start refund process` only when `can_prepare_refund = true`. Clicking the command calls the same-origin frontend proxy route for `POST /api/purchases/{purchase_id}/refund/request`, which forwards to the FastAPI backend. After successful preparation, the help layer removes the command, refreshes the current route, and lets the purchase detail page visualize updated lifecycle state. Backend services remain responsible for deciding whether refund actions are allowed.

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
* Purchase detail records with refund lifecycle state
* Policies
* Support Sessions
* AI Events
* Voice Transcripts

Refund state is not stored in a standalone `refunds` table. Refund eligibility is computed from persisted purchase and purchase-detail state. Each purchase type owns the fields required by its own refund policy:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

The backend policy layer reads those records, evaluates the product-specific policy, and persists approved lifecycle changes back to the owning detail table.

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
* Refund workflows backed by purchase detail state
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

## Refund Evaluation Flow

Refund requests follow a database-backed deterministic path:

```text
User requests refund
        |
        v
Backend loads purchase
        |
        v
Backend loads matching purchase detail record
        |
        v
Backend verifies refund window
        |
        v
Backend evaluates product-specific policy
        |
        v
Backend executes refund strategy
        |
        v
Backend persists updated detail-table refund state
```

The AI agent may explain outcomes and orchestrate tools, but it does not infer refund eligibility independently.

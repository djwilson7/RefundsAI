# 00-project.md

# Project Overview

## Vision

RefundsAI is a production-inspired customer support platform for refund workflows.

The AI assistant is the conversational interface. It can understand customer intent,
gather context, call backend tools, explain outcomes, and guide approved workflows.
It is not the business authority.

Backend services, deterministic policy code, and persisted database facts decide
refund eligibility and refund lifecycle transitions.

## Current Implementation

Implemented surfaces:

* Next.js customer portal in `apps/web`.
* FastAPI backend in `apps/api`.
* Supabase PostgreSQL migrations and seed data.
* Mock customer and administrator entry paths.
* Customer purchase history and purchase detail screens.
* Type-specific purchase detail presentation for digital, physical, and subscription purchases.
* Backend refund workflow evaluation, preparation, issuance, digital code redemption, and physical carrier acceptance.
* LangGraph-backed chat endpoint for purchase facts, refund policy, refund eligibility, and confirmation-gated refund actions.
* Persisted model audit sessions and ordered audit events for chat execution.
* Admin audit session list, session detail timeline, token/latency summaries, and realtime SSE-backed refresh.

Current project state:

* The core technical challenge implementation is complete through text chat, deterministic refund workflow execution, and administrative auditability.
* Further work should be treated as polish, model-quality tuning, user experience refinement, validation hardening, or explicitly deferred production scope.

Not yet productionized:

* Real authentication and authorization.
* Real payment processing.
* Production-grade support case management.
* Voice capture, transcription, and voice responses.
* Production deployment hardening.

## Core Product Rule

Refund state belongs to the purchase type that owns the operational lifecycle:

* Digital refund state: `digital_purchase_details`
* Physical refund state: `physical_purchase_details`
* Subscription refund state: `subscription_purchase_details`

The shared `purchases` table stores purchase history plus workflow summary facts such
as `status`, `refund_requested_at`, `refunded_at`, `refund_amount_cents`, and
`refund_outcome`.

No standalone `refunds` table should be introduced under the current architecture.

## Primary Interfaces

### Customer Portal

Customers can:

* Enter through mock login.
* View account summary metrics.
* Browse seeded purchase history.
* Open one stable purchase detail route: `/purchase-details/[purchaseId]`.
* Ask the shared help panel about purchases, policy, eligibility, and refund process actions.
* Confirm eligible refund process actions through the chat workflow.

### Admin Dashboard

The Admin Dashboard is designed to serve as an **AI Auditability and Observability Suite**, rather than a customer account management panel. 

The primary goal is providing live monitoring and historical review of the AI agent's decision-making process:
* **Audit Session Overview**: Displays a reverse-chronological timeline of customer-agent chat sessions.
* **Audit Session Details**: Direct deep-dive visibility into a single chat interaction session, rendering the customer prompt, final response, chosen workflow family, context resolution parameters, token usage metrics, latency, and real-time execution steps.
* **Realtime Event Streaming**: WebSockets or SSE channels stream LangGraph trace events dynamically to the admin screen, creating a live timeline of the model's reasoning.

## Technology Stack

Frontend:

* Next.js
* TypeScript
* React
* CSS modules and global CSS
* Framer Motion for motion where used

Backend:

* FastAPI
* Python
* Pydantic response schemas
* psycopg for PostgreSQL access

Database:

* Supabase PostgreSQL
* Ordered Python migration modules
* Idempotent seed steps

AI:

* OpenAI chat completions client
* LangGraph workflow
* Backend-owned tool execution

## Repository Philosophy

This repository is documentation-first.

`.ai-context/` is the authoritative project context. Source code, migrations, tests,
and package scripts remain the implementation source of truth. When documentation and
implementation drift, inspect the code and update the docs rather than preserving stale
or generic guidance.

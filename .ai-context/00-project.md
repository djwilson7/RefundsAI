# 00-project.md

# Project Overview

## Vision

Build a production-inspired AI customer support platform that automates business decisions wherever company policy explicitly permits while preserving deterministic business logic, policy enforcement, and operational governance.

The language model acts as the conversational interface between users and business systems. It is responsible for understanding intent, gathering context, orchestrating backend tools, communicating outcomes, and escalating interactions when policy or customer circumstances require human intervention.

Business policy remains the authoritative source for operational decisions.

---

## Goals

This project is designed to demonstrate:

* AI-assisted customer support workflows.
* Deterministic policy enforcement.
* Tool-driven language model orchestration.
* Transparent AI behavior and auditability.
* Clean separation between conversational AI and business logic.
* Production-oriented software architecture.

---

## Scope

The application consists of two primary interfaces:

### Customer Portal

Customers can:

* View account information.
* Browse purchase history.
* Inspect refund eligibility.
* Request refunds.
* Interact with an AI assistant through text or voice.

### Admin Operations Dashboard

Administrators can:

* View operational metrics.
* Verify customer identity before accessing customer data.
* Review customer purchase and support history.
* Audit AI interactions and execution traces.
* Ask conversational questions about customer activity and operational data.

The implementation intentionally focuses on AI product behavior rather than building a complete e-commerce platform.

---

## Technical Stack

### Frontend

* Next.js
* TypeScript
* Tailwind CSS

### Backend

* FastAPI
* Python

### Database

* Supabase PostgreSQL

### AI Services

* OpenAI APIs
* Function Calling
* Voice Transcription

---

## Repository Philosophy

This repository follows a documentation-first development approach.

The `.ai-context/` directory is the authoritative source for project architecture, implementation boundaries, business logic, engineering standards, and system behavior.

All contributors—human or AI—should consult the relevant context documents before making implementation decisions.

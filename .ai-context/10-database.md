# 10-database.md

# Database Schema

## Purpose

This document defines the database schema, entity relationships, data ownership, and schema evolution throughout the project.

The database remains the authoritative source for all persistent business state.

---

# Database Principles

* The database is the system of record.
* Business services own all database interactions.
* The frontend never communicates directly with the database.
* The language model retrieves database information exclusively through backend tools.

---

# Entity Documentation

Each entity should document:

* Purpose
* Owner
* Relationships
* Frontend Visibility
* Backend Visibility

Example:

```text id="52lzww"
customers

Purpose
Stores customer account information.

Owner
Backend

Relationships
orders
support_sessions
account_ledger

Frontend
Customer profile information only.

Backend
Full record.
```

---

# Relationships

Document relationships between entities as they are introduced.

Example:

```text id="t11z5l"
Customer
    │
    ├── Orders
    │      └── Order Items
    │               └── Refund Eligibility
    │
    ├── Support Sessions
    │      └── Support Messages
    │
    ├── Account Ledger
    │
    └── AI Events
```

---

# Frontend Data

Only data required by the user interface should be exposed through backend APIs.

Sensitive or internal fields should remain backend-only.

---

# Backend Data

Internal business state, audit information, policy metadata, and implementation-specific fields remain accessible only through backend services.

---

# Schema Changes

Structural database changes should be recorded here.

Document:

* Date
* Change
* Reason

Example:

```text id="c6x1js"
2026-07-03

Added refund_eligibility table.

Reason

Support deterministic policy evaluation without requiring the language model to infer refund state.
```

---

# Migration Philosophy

Schema changes should preserve data integrity whenever practical.

Every migration should be accompanied by corresponding updates to:

* Database documentation
* API contracts
* Business logic documentation
* Tests (when applicable)

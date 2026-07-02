# 11-tools.md

# Tool Specifications

## Purpose

This document defines the tools available to the language model and the contract for each tool.

All interactions between the language model and backend services should occur through documented tools.

As new tools are introduced, they should be added to this document.

---

# Tool Design Principles

* Tools provide the language model with authoritative backend information.
* Each tool should have a single, well-defined responsibility.
* Tools should be deterministic and repeatable.
* Tools should validate inputs before execution.
* Business logic remains within backend services, not the language model.

---

# Tool Documentation

Each tool should document:

* Name
* Purpose
* Supported Roles
* Inputs
* Outputs
* Read/Write Behavior
* Side Effects
* Possible Errors

Example:

```text
Tool
get_purchase_history

Purpose
Retrieve a customer's purchase history.

Roles
Customer
Administrator

Inputs
customer_id

Outputs
List of purchases

Behavior
Read Only

Side Effects
None

Errors
CUSTOMER_NOT_FOUND
UNAUTHORIZED
```

---

# Tool Categories

Tools should be organized into logical groups.

* Customer
* Purchases
* Refunds
* Policies
* Support
* Administration
* Audit
* Escalation

---

# Read vs Write Tools

Every tool should clearly indicate whether it is:

* **Read Only** – Retrieves information without modifying system state.
* **Mutating** – Creates, updates, or modifies business state.

Mutating tools should execute only after deterministic backend validation and policy enforcement.

---

# Role-Based Access

Tools should explicitly define which personas may invoke them.

Available roles include:

* Customer
* Administrator
* AI Assistant

Role restrictions should be enforced by backend services before tool execution.

---

# Tool Evolution

As the application grows, this document should remain synchronized with the implemented tool surface.

Adding, modifying, or removing tools should include corresponding updates to this document to preserve a clear contract between the language model and backend services.

# 04-personas.md

# Personas

## Purpose

This document defines the primary actors within the system, their responsibilities, permissions, and operational boundaries.

---

# Customer

## Description

The customer is the primary end user of the platform.

Customers interact with the system through the Customer Portal and AI assistant to manage purchases, request refunds, and receive support.

### Responsibilities

* View account information.
* Browse purchase history.
* View refund eligibility.
* Request refunds.
* Interact with the AI assistant.
* Review previous support conversations.

### Permissions

* Access only their own account.
* View only their own purchases and support history.
* Initiate support and refund requests.

### Restrictions

* Cannot access administrative functionality.
* Cannot override business policy.
* Cannot modify authoritative business data.

---

# Administrator

## Description

Administrators manage customer support operations through the Admin Dashboard.

Their role is to review customer activity, investigate support interactions, audit AI behavior, and resolve escalated cases.

### Responsibilities

* Monitor operational metrics.
* Verify customer identity.
* Review customer history.
* Inspect AI execution logs.
* Review escalated cases.
* Resolve support requests.

### Permissions

* Access the Admin Dashboard.
* View customer information after successful verification.
* Review AI conversations and audit history.
* Access operational reporting.

### Restrictions

* Customer-specific data should only be accessible after customer verification.
* Administrative actions remain subject to business policy.

---

# AI Assistant

## Description

The language model serves as the conversational interface between users and business systems.

Its purpose is to improve customer and administrator experiences through natural language interaction while operating within deterministic system boundaries.

### Responsibilities

* Understand user intent.
* Gather relevant context.
* Select backend tools.
* Explain business policy.
* Execute approved workflows.
* Communicate outcomes.
* Escalate interactions when required.

### Permissions

* Access backend tools.
* Retrieve authoritative business data.
* Initiate policy-approved workflows.
* Support both customer and administrator interactions.

### Restrictions

* Is not the authoritative source for business decisions.
* Cannot override policy.
* Cannot directly modify business state.
* Cannot bypass backend validation.
* Must rely on backend tools for authoritative information.

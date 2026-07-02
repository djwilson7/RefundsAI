# 07-documentation.md

# Documentation Standards

## Purpose

This document defines the documentation expectations for the repository.

Documentation is considered part of implementation. Changes to system behavior, architecture, or business logic should be reflected in the appropriate documentation.

---

# Documentation Philosophy

Documentation should explain:

* What was implemented.
* Why it exists.
* How it is intended to be used.

Documentation should improve understanding rather than duplicate the implementation.

---

# Inline Comments

Inline comments should be used to explain:

* Non-obvious business logic.
* Architectural decisions.
* Design tradeoffs.
* Complex algorithms.
* Edge case handling.

Avoid comments that simply describe obvious syntax or restate the code.

---

# Code Documentation

Public modules, services, classes, and functions should include descriptive documentation where appropriate.

Documentation should clearly communicate:

* Purpose
* Inputs
* Outputs
* Side effects
* Expected behavior

---

# Repository Documentation

Documentation should remain synchronized with implementation.

Update documentation whenever changes affect:

* Architecture
* Business logic
* API contracts
* Database schema
* Tool behavior
* Security boundaries

The `.ai-context/` directory remains the authoritative source for project context and should be updated whenever repository knowledge changes.

---

# Documentation Quality

Documentation should be:

* Clear
* Concise
* Accurate
* Maintainable
* Focused on intent rather than implementation details

Well-written documentation should help both engineers and AI agents understand the reasoning behind the system without requiring them to infer behavior from the codebase alone.

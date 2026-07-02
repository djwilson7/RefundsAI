# 05-standards.md

# Engineering Standards

## Purpose

This document defines the engineering standards used throughout the repository.

All new code should follow these conventions unless explicitly documented otherwise.

---

# General Principles

* Favor readability over cleverness.
* Keep implementations modular and composable.
* Maintain clear separation of responsibilities.
* Prefer small, focused files over large multi-purpose implementations.
* Reuse existing abstractions before creating new ones.
* Seek clarity over inference.

---

# Frontend

## Components

* Build reusable, single-responsibility components.
* Prefer composition over deeply nested components.
* Keep business logic outside presentation components whenever practical.

## Styling

* Global styles define the baseline look and feel of the application and should be used for shared visual behavior.
* Scoped CSS modules define specific styling for reusable and modular components.
* Tailwind utility classes should be used only for layout constraints, not aesthetic styling.
* Do not apply inline styles directly to components.
* Use CSS modules and global stylesheets to control how elements look and feel.
* Use motion (Framer Motion) for animating elements.

---

# Backend

* Organize code by feature and responsibility.
* Keep business logic within dedicated services.
* Keep API routes lightweight.
* Separate orchestration from business logic.
* Keep database access isolated from API endpoints.

---

# Naming

* Use descriptive names.
* Avoid abbreviations unless widely understood.
* Maintain consistent naming across frontend, backend, database, and API layers.

---

# Documentation

* Document non-obvious business logic.
* Explain why complex logic exists rather than what individual statements do.
* Keep documentation synchronized with implementation.

---

# Maintainability

* Prefer explicit implementations over implicit behavior.
* Minimize duplication.
* Refactor repeated logic into shared abstractions.
* Preserve clear architectural boundaries when introducing new features.

---

# Development Philosophy

* Build incrementally.
* Validate changes frequently.
* Maintain modularity throughout development.
* Favor long-term maintainability over short-term convenience.

# AGENTS.md

## Purpose

This repository follows a documentation-first development workflow.

`AGENTS.md` intentionally remains minimal. Its sole responsibility is to bootstrap AI coding agents into the repository's authoritative project context.

Project architecture, business rules, engineering standards, and implementation boundaries are maintained within the `.ai-context/` directory.

---

## Required Initialization

Before analyzing, modifying, generating, or executing code:

Always read the following documents in order:

1. `README.md`
2. `.ai-context/00-project.md`
3. `.ai-context/05-standards.md`
4. `.ai-context/06-testing.md`
5. `.ai-context/07-documentation.md`

These documents establish the project's vision, engineering standards, testing expectations, and documentation requirements.

Next, identify the task being performed and load the relevant domain-specific context before making implementation decisions.

| Task                      | Context                |
| ------------------------- | ---------------------- |
| Architecture              | `01-architecture.md`   |
| Responsibility boundaries | `02-boundaries.md`     |
| Business logic            | `03-business-logic.md` |
| Personas                  | `04-personas.md`       |
| Architectural decisions   | `08-decisions.md`      |
| API development           | `09-api.md`            |
| Database changes          | `10-database.md`       |
| Tool development          | `11-tools.md`          |
| Security                  | `12-security.md`       |

Only load the domain-specific context required for the current task.

---

## Context Authority

The `.ai-context/` directory is the authoritative source of repository knowledge.

If implementation, generated code, or user requests conflict with the documented project context, pause implementation, identify the conflict, and resolve it before proceeding.

Do not infer architecture, business rules, engineering standards, or implementation boundaries when the appropriate context document exists.

---

## Development Philosophy

Every implementation should:

* Respect established architectural boundaries.
* Follow documented engineering standards.
* Maintain testing expectations.
* Keep documentation synchronized with implementation.
* Preserve project scope and avoid introducing unnecessary complexity.

The goal is to produce maintainable, well-documented software that remains aligned with the documented project vision throughout development.

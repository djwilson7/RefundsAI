# Developer Insights

## Purpose

This document captures engineering reasoning, implementation tradeoffs, and system-design thinking throughout the project.

It is not the authoritative source for project rules. Those live in `.ai-context/`.

This file explains why the project evolves the way it does.

---

## Insight 001 — Context Before Code

Before scaffolding the application, the project establishes a context layer that defines vision, architecture, business boundaries, testing expectations, API contracts, database ownership, tool specifications, and security boundaries.

Reason:

This project is a presentation-grade technical challenge, not a disposable prototype. Establishing context first allows faster implementation later while reducing architectural drift, unnecessary rewrites, and model-generated scope creep.

Tradeoff:

This delays initial coding, but improves implementation velocity once development begins.

---

## Insight 002 — Agent Behavior First

The primary evaluation target is the agent workflow.

The project prioritizes:

- policy-governed refund decisions
- tool orchestration
- edge-case denial behavior
- auditability
- trace visibility

Reason:

The Loom evaluation specifically asks for a live agent demo, code tour, and reasoning logs. The user interface supports the agent workflow, but the agent workflow is the core product proof.

---

## Insight 003 — Local-First Development

The project is scoped for local development rather than immediate deployment.

Reason:

The technical challenge requires a GitHub repository, README, and Loom walkthrough. Local reproducibility is more important than deployment infrastructure during the early milestones.

Tradeoff:

A hosted demo may be added later, but deployment should not block core agent functionality.
# 04-personas.md

# Personas

## Customer

The customer uses the Customer Portal and help panel to inspect purchase history and
work through refund questions.

Current implementation:

* Mock customer is selected on `/`.
* `/user-home?customerId=...` loads profile and purchase history from FastAPI.
* Purchase detail routes load backend detail state and refund workflow state.
* The help panel sends chat messages with compact page and conversation context.

Permissions:

* View the selected mock customer's profile and purchases.
* Ask account, order, purchase, policy, and refund questions.
* Confirm eligible refund process actions using the exact canonical command supplied by the assistant.

Restrictions:

* Cannot access admin functionality.
* Cannot override backend policy.
* Cannot directly modify purchase, refund, or financial state.
* Cannot provide authoritative eligibility, amount, outcome, or deadline values.

## Administrator

The administrator represents support operations staff focused on AI auditability.

Current implementation:

* Mock admin can enter `/admin-home`.
* `/admin-home` lists persisted model audit sessions with summary metrics.
* `/admin/sessions/[sessionId]` separates request identity, process performance, and
  token usage; explains each backend tool; and presents every ordered event as a
  readable execution narrative.
* Admin screens refresh from realtime audit event notifications through the SSE proxy.

Deferred production responsibilities:

* Verify customers before viewing customer-specific data.
* Review broader purchase and support history.
* Resolve escalated cases.
* Review production operational metrics.

Restrictions:

* Customer-specific data should require verification.
* Administrative actions remain subject to deterministic policy.

## AI Assistant

The AI assistant is a conversational layer over backend tools and services.

It may:

* Interpret customer language.
* Request read-only backend tools.
* Explain purchase facts, refund policy, and refund eligibility from backend data.
* Guide confirmation-gated refund actions.

Some “assistant” responses are backend-authored transactional messages. This is
intentional when the customer has submitted an exact confirmation and no additional
language reasoning is needed.

It may not:

* Act as the source of truth for policy or eligibility.
* Access the database directly.
* Choose or widen customer identity.
* Mutate refund state without backend validation and exact customer confirmation.
* Claim a refund action completed unless the backend mutation completed.

## Backend System

For implementation decisions, treat the backend as an actor with explicit authority.

It owns:

* Database access.
* Policy evaluation.
* Workflow transitions.
* Tool execution.
* API response contracts.
* Conflict detection for duplicate or stale writes.
* Deterministic transactional responses after verified mutations.

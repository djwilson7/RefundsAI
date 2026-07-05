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
* Refund tools should expose backend-evaluated eligibility from purchase detail state.
* Refund tools must not let the model submit or override authoritative refund state.

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

Refund mutating tools should update only the owning purchase detail table for the product type being processed:

* digital refund actions update `digital_purchase_details`
* physical refund actions update `physical_purchase_details`
* subscription refund actions update `subscription_purchase_details`

No tool should create or depend on a standalone `refunds` table.

Tools should not send database-derived refund deadlines. PostgreSQL triggers compute refund window fields from persisted purchase/detail state.

The current frontend help panel includes temporary manual `Prep Refund` and `Issue Refund` commands that call backend refund workflow endpoints through same-origin frontend proxy routes. These controls exist to validate backend workflow state and frontend lifecycle displays before the agent layer is active. Future refund tools should replace that manual path rather than duplicate it. The intended long-term flow is for the agent to call deterministic backend tools to initiate approved refund preparation and issuance, while purchase detail pages continue to render the resulting backend state.

The current `POST /api/chat` endpoint now runs the first read-only AI tool surface for purchase-history intelligence. The LangGraph workflow may call `get_customer_purchase_history`, `get_purchase_count_by_amount_threshold`, and `get_purchase_history_by_date_range` through backend application services and return model-generated plain-text answers about account, purchase, order, account-activity, and refund-flow topics. If the model requests no supported tool, the backend should execute `get_purchase_count_by_amount_threshold` for deterministic amount-threshold purchase questions, execute `get_purchase_history_by_date_range` for deterministic date-range purchase questions, execute `get_customer_purchase_history` for other deterministic account-domain fallback intents, and skip account tools for unrelated customer messages. If the model requests the broad `get_customer_purchase_history` tool for a resolvable date-bounded purchase question, the backend should override that selection and execute `get_purchase_history_by_date_range` instead. Broad purchase history is the fallback, not the default, when a narrower deterministic tool applies. Account-fact responses must be blocked unless an authoritative tool result exists. Malformed pseudo-tool text from the model is invalid output and must not be treated as reasoning or a valid tool call. The endpoint must not return Markdown-formatted assistant content, evaluate refund policy, capture voice input, persist conversation logs, or mutate business state. Backend chat logs should include sequential trace events for the observable model/tool orchestration path, including the model request package, requested tool calls, invalid model output, backend-enforced tool execution inputs, skipped tool decisions, blocked response decisions, tool results, and final generated response.

Tool
get_customer_purchase_history

Purpose
Retrieve one customer's purchase history and backend-computed aggregate counts and totals for read-only AI responses.

Roles
Customer
AI Assistant

Inputs
customer_id

Outputs
Sanitized purchase rows plus total purchase count, total amount in cents, model-facing dollar display strings, counts/totals by purchase type, and counts/totals by purchase status.

Behavior
Read Only. The active chat request supplies `customer_id`; the model must not choose or override customer identity through tool arguments. Database money values remain cent-based. Dollar fields in tool output are derived boundary/display values for model explanation only.

Side Effects
None

Errors
CUSTOMER_NOT_FOUND
DATABASE_NOT_CONFIGURED

Tool
get_purchase_history_by_date_range

Purpose
Retrieve a customer's purchases and backend-computed aggregate counts and totals for an inclusive local date range.

Roles
Customer
AI Assistant

Inputs
start_date in `YYYY-MM-DD`
end_date in `YYYY-MM-DD`
timezone, such as `America/Chicago`

Outputs
date_range with start_date, end_date, label, and timezone; sanitized purchase rows with amount/date display fields; total purchase count; total amount in cents and dollars; counts/totals by purchase type; and counts/totals by purchase status.

Behavior
Read Only. The active chat request supplies `customer_id`; the model must not choose or override customer identity through tool arguments. Date inputs are inclusive local dates. The backend resolves relative phrases in the customer timezone before querying and converts local dates to a half-open timestamp range: `purchased_at >= start_date at 00:00:00 local time` and `purchased_at < day_after_end_date at 00:00:00 local time`. Do not use SQL `BETWEEN` for timestamp ranges. A business week starts Sunday at 00:00:00 local time and ends Saturday at 23:59:59 local time. "This week" means Sunday of the current local week through the current local date. "Last week" means the full previous Sunday-through-Saturday week. If the customer local date is Sunday, July 5, 2026, "this week" resolves to July 5, 2026 through July 5, 2026, and "last week" resolves to June 28, 2026 through July 4, 2026. "First week of May" means May 1 through May 7.

Side Effects
None

Errors
CUSTOMER_NOT_FOUND
DATABASE_NOT_CONFIGURED

Tool
get_purchase_count_by_amount_threshold

Purpose
Count a customer's purchases matching an amount threshold and return deterministic aggregate facts for filtered purchase-history questions.

Roles
Customer
AI Assistant

Inputs
threshold_cents
comparison, one of `gt`, `gte`, `lt`, or `lte`

Outputs
count, matching_purchase_ids, total_amount_cents, total_amount_dollars, threshold_cents, threshold_dollars, and comparison.

Behavior
Read Only. The active chat request supplies `customer_id`; the model must not choose or override customer identity through tool arguments. Backend fallback parsing may execute this tool without a model tool call for supported amount-threshold questions such as "How many purchases have I made over $100?" User-facing dollar thresholds are converted to cents at the chat boundary before filtering, and all comparisons are performed against cent-based purchase amounts.

Side Effects
None

Errors
CUSTOMER_NOT_FOUND
DATABASE_NOT_CONFIGURED

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

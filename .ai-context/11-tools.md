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

---

# Active Chat Tool Surface

The current `POST /api/chat` endpoint exposes only read-only tools to the language model.

| Category | Tool | Purpose | Mutates State |
| --- | --- | --- | --- |
| Purchases | `get_customer_purchase_history` | Retrieve active-customer purchase rows and aggregates. | No |
| Purchases | `get_purchase_history_by_date_range` | Retrieve active-customer purchases for an inclusive local date range. | No |
| Purchases | `get_purchase_count_by_amount_threshold` | Count active-customer purchases matching an amount threshold. | No |
| Policies | `get_refund_policy` | Retrieve deterministic refund policy sections. | No |
| Refunds | `get_refund_eligibility` | Retrieve backend-evaluated refund eligibility and workflow state. | No |

No currently callable chat tool may prepare, submit, process, issue, cancel, or otherwise mutate a refund workflow. Refund workflow mutation remains a Phase 4 boundary.

---

# Shared Chat Orchestration Rules

## Identity and Authorization

The active chat request supplies `customer_id`. The model must not choose, override, or widen customer identity through tool arguments.

Tools that inspect purchase history or refund eligibility require an active customer context. General refund policy lookup may run without customer context because it is not account-specific.

## Deterministic Fallback Routing

If the model requests no supported tool for a supported account, policy, or eligibility question, the backend executes the narrowest deterministic tool itself.

If the model requests broad purchase history for a resolvable date-bounded, policy, or eligibility question, the backend overrides that request with the narrower deterministic tool.

Broad purchase history is the fallback when no narrower deterministic tool applies.

The chat workflow resolves each customer message into a deterministic conversation object plus operation before selecting a workflow. Conversation objects include explicit product references, demonstrative references to the active result set, purchase type, date range, amount threshold, page purchase, active purchase, active result set, full purchase history, and unknown. Operations include count, list, ranked selection, policy, eligibility, refund start, explanation, and unknown. The object-operation lookup decides whether the turn is an account fact, refund policy lookup, read-only eligibility lookup, blocked future mutation, or clarification.

## Conversation and Page Context

The endpoint accepts compact page context for either the all-purchases surface or one purchase-detail surface by purchase id only. Full rendered page content must not be sent to the model.

The endpoint returns compact conversation state for follow-up routing:

* `selected_purchase_type`
* `selected_product`
* `selected_purchase_id`
* `selected_purchase_ids`
* `selected_scope_label`
* `selected_policy_scope`
* `selected_date_range`
* `selected_refund_purchase_ids`
* `selected_refund_context`
* `active_refund_context`
* `active_result_set`
* `active_workflow`
* `current_page`

The chat graph injects compact model-visible context into both tool-selection and final-response model requests when it is relevant. This context may include selected purchase type, product, purchase id, selected purchase id counts with short ids, active result set label and count, policy scope, refund context, active refund context, current purchase-detail reference, summarized tool data, and blocked-action context. It must not include the full prior transcript or full rendered page content.

Before honoring any model-requested tool, the backend resolves authoritative context in this order: explicit named product references, demonstrative or pronoun references to an active purchase/result set, explicit purchase type, explicit date range, explicit amount threshold, page purchase, active purchase, active result set, full purchase history, then unknown or clarification. The model may interpret language, but it does not decide which purchase, scope, policy, or workflow target is authoritative.

Aggregate and list results become the active purchase scope for follow-up resolution. Examples include purchase-type groups, amount-threshold groups, date ranges, and any other filtered purchase-history result that returns `selected_purchase_ids`. These results also store `selected_scope_label` for customer-safe follow-up phrasing and `active_result_set` as an ID-only state object with `type`, `purchase_ids`, `sort`, and `label`.

When `active_result_set` is the primary final-response answer source, the final-response package hydrates the selected ids into safe display fields already available to the model, such as product name, purchase type, display amount, status, and purchase date. The hydrated item list is model-request context only; it must not be written back into `conversation_state.active_result_set`.

Scoped ranking follow-ups using "one", "that one", "those", "last one", "first one", "latest", "most recent", "newest", "oldest", "earliest", "cheapest", or "most expensive" resolve inside the selected purchase id set first when it exists. "Oldest", "earliest", and "first" rank by the lowest `purchased_at`; "latest", "most recent", "newest", and "last one" rank by the highest `purchased_at`; "cheapest" and "most expensive" rank by `amount_cents`. The backend uses global ranked purchase history only when no selected set exists.

Ranking-only follow-ups are account-fact questions, not refund-policy or refund-eligibility questions. The backend must not call `get_refund_policy` or `get_refund_eligibility` for a ranking-only follow-up unless the user explicitly asks about refund policy, return policy, cancellation rules, refundability, eligibility, approval, or the refund process.

Whenever the backend resolver identifies exactly one concrete purchase, it updates `selected_purchase_id`, `selected_product`, and `selected_purchase_type` from that backend purchase row. Assistant prose is not parsed to infer state.

After `get_refund_eligibility` returns exactly one resolved purchase, the endpoint stores `active_refund_context` with the evaluated purchase id, product name, purchase type, eligibility flag, workflow stage, next action, and reason codes. If the eligible physical workflow next action is `generate_return_label`, the active context stage is `awaiting_return_label` and next action is `generate_return_label`. Follow-up workflow continuation phrases such as "generate the return label", "start the return", "return the item", "proceed", or "yes, continue" must resolve against this active context. If the active context is missing, the backend asks the customer to confirm the product or order number before continuing. Phase 3 still does not call refund mutation tools; when the next action is known but mutation tooling is not wired, the assistant says that workflow action is not wired yet.

Explicit product-name follow-ups such as "Developer Toolkit" escape narrowed selected sets and resolve against the active customer's full backend purchase rows using exact, normalized, partial, fuzzy, SKU, order-number, or purchase-id matching.

Named product references must resolve unambiguously to an actual purchase before product-specific policy or eligibility lookup. If no match is found or multiple product-name matches are plausible, the backend must not infer purchase type, must not call `get_refund_policy` or `get_refund_eligibility`, and must ask for clarification.

Purchase-detail page references such as "this product", "this item", "this purchase", or "this order" resolve to `page_context.purchase_id` before selected purchase state, selected refund state, or product-name matching.

## Response Guards

Account-fact responses must be blocked unless an authoritative tool result exists.

Refund policy explanations must use `get_refund_policy` results.

Refund eligibility explanations must use `get_refund_eligibility` results. The model must not infer, override, or calculate eligibility independently.

Malformed pseudo-tool text from the model is invalid output and must not be treated as reasoning or a valid tool call.

The endpoint must not return Markdown-formatted assistant content, capture voice input, persist conversation logs, or mutate business state.

Customer-facing assistant content must not expose backend routing terms such as selected context, selected set, resolver, tool, state, purchase ids, node, or graph.

## Logging

Backend chat logs should include sequential trace events for the observable orchestration path:

* model request package
* requested tool calls
* invalid model output
* backend-enforced tool execution inputs
* skipped tool decisions
* blocked response decisions
* tool results
* final generated response

Structured application log records should retain full event data for tests and future audit surfaces. Console output should render those events as concise human-readable step summaries and avoid dumping full nested prompt, tool, or response payloads. Console summaries should still show the model-relevant context: compact selected conversation state, current page or resolved page reference, intent flags, tool result summaries provided to the model, and blocked-action reasons.

Final-response console summaries should distinguish raw tool results from active-result-set context. Raw purchase-history results may be summarized as totals and counts, while active-result-set context should show its label/count and, when it is the primary answer source, a capped `items_preview` containing only safe model-visible display fields.

---

# Callable Tool Contracts

## Purchases

### `get_customer_purchase_history`

**Purpose**

Retrieve one customer's purchase history and backend-computed aggregate counts and totals for read-only AI responses.

**Supported Roles**

Customer, AI Assistant

**Inputs**

* `customer_id`

**Outputs**

* sanitized purchase rows
* total purchase count
* total amount in cents
* model-facing dollar display strings
* counts and totals by purchase type
* counts and totals by purchase status

**Behavior**

Read Only. The active chat request supplies `customer_id`; the model must not choose or override it. Database money values remain cent-based. Dollar fields are derived boundary/display values for model explanation only.

**Side Effects**

None

**Errors**

`CUSTOMER_NOT_FOUND`, `DATABASE_NOT_CONFIGURED`

### `get_purchase_history_by_date_range`

**Purpose**

Retrieve a customer's purchases and backend-computed aggregate counts and totals for an inclusive local date range.

**Supported Roles**

Customer, AI Assistant

**Inputs**

* `start_date` in `YYYY-MM-DD`
* `end_date` in `YYYY-MM-DD`
* `timezone`, such as `America/Chicago`

**Outputs**

* `date_range` with start date, end date, label, and timezone
* sanitized purchase rows with amount/date display fields
* total purchase count
* total amount in cents and dollars
* counts and totals by purchase type
* counts and totals by purchase status

**Behavior**

Read Only. The active chat request supplies `customer_id`; the model must not choose or override it.

Date inputs are inclusive local dates. The backend resolves relative phrases in the customer timezone before querying and converts local dates to a half-open timestamp range:

* `purchased_at >= start_date at 00:00:00 local time`
* `purchased_at < day_after_end_date at 00:00:00 local time`

Do not use SQL `BETWEEN` for timestamp ranges.

A business week starts Sunday at 00:00:00 local time and ends Saturday at 23:59:59 local time.

* "This week" means Sunday of the current local week through the current local date.
* "Last week" means the full previous Sunday-through-Saturday week.
* If the customer local date is Sunday, July 5, 2026, "this week" resolves to July 5, 2026 through July 5, 2026, and "last week" resolves to June 28, 2026 through July 4, 2026.
* "First week of May" means May 1 through May 7.

**Side Effects**

None

**Errors**

`CUSTOMER_NOT_FOUND`, `DATABASE_NOT_CONFIGURED`

### `get_purchase_count_by_amount_threshold`

**Purpose**

Count a customer's purchases matching an amount threshold and return deterministic aggregate facts for filtered purchase-history questions.

**Supported Roles**

Customer, AI Assistant

**Inputs**

* `threshold_cents`
* `comparison`, one of `gt`, `gte`, `lt`, or `lte`

**Outputs**

* `count`
* `matching_purchase_ids`
* `total_amount_cents`
* `total_amount_dollars`
* `threshold_cents`
* `threshold_dollars`
* `comparison`

**Behavior**

Read Only. The active chat request supplies `customer_id`; the model must not choose or override it.

Backend fallback parsing may execute this tool without a model tool call for supported amount-threshold questions such as "How many purchases have I made over $100?"

User-facing dollar thresholds are converted to cents at the chat boundary before filtering, and all comparisons are performed against cent-based purchase amounts.

**Side Effects**

None

**Errors**

`CUSTOMER_NOT_FOUND`, `DATABASE_NOT_CONFIGURED`

## Policies

### `get_refund_policy`

**Purpose**

Retrieve deterministic RefundsAI refund policy sections scoped to the customer's policy question.

**Supported Roles**

Customer, AI Assistant

**Inputs**

* `scope`, one of `general`, `product_type`, `funds_release`, or `administrative_review`
* `purchase_type`, optional one of `digital`, `physical`, or `subscription`

**Outputs**

* `scope`
* `purchase_type`
* `effective_date`
* `sections`
* `source`

**Behavior**

Read Only.

General policy questions return all product-type rules plus shared processing, administrative-review, and update sections.

Product-specific questions return only the relevant product-type policy.

Funds-release questions return refund processing policy and any relevant product-specific prerequisite when a product type is named.

Administrative-review questions return review policy and any relevant product-specific policy when a product type is named.

This tool does not inspect customer purchases, calculate eligibility, or mutate refund workflow state.

**Side Effects**

None

**Errors**

None

## Refunds

### `get_refund_eligibility`

**Purpose**

Return backend-evaluated read-only refund eligibility and workflow state for backend-resolved purchase ids.

**Supported Roles**

Customer, AI Assistant

**Inputs**

* `purchase_ids`, a non-empty list of purchase ids resolved by backend chat context
* `context`, a compact label such as `product`, `digital`, `current_page`, `selected_set`, `date_range`, or `all_purchases`

**Outputs**

Top-level output:

* `customer_id`
* `context`
* `requested_purchase_ids`
* `resolved_purchase_ids`
* `purchase_count`
* `eligible_count`
* `blocked_count`
* `prepared_count`
* `issued_count`
* `purchases`

Each purchase result includes:

* purchase id
* order number
* SKU
* product name
* purchase type
* status
* amount fields
* purchase date display
* `refund_stage`
* `can_enter_refund_workflow`
* `can_prepare_refund`
* `can_issue_funds`
* `required_action`
* `refund_outcome`
* refundable amount fields
* `reasons`
* safe `policy_facts` from the backend workflow decision

**Behavior**

Read Only. The active chat request supplies `customer_id`; the model must not choose or override it.

The backend resolves user text to active customer purchase ids before executing the tool and filters requested ids against that active customer's purchase history.

The tool calls `ApplicationService.get_refund_workflow` for each resolved purchase and returns deterministic decisions for model explanation.

The assistant may explain that a purchase is eligible to begin refund handling, blocked, prepared, or issued. It must not prepare, submit, process, issue, cancel, or otherwise mutate a refund workflow.

**Side Effects**

None

**Errors**

`CUSTOMER_NOT_FOUND`, `DATABASE_NOT_CONFIGURED`

---

# Non-Tool Refund Workflow Boundaries

Every tool should clearly indicate whether it is:

* **Read Only** - Retrieves information without modifying system state.
* **Mutating** - Creates, updates, or modifies business state.

Mutating tools should execute only after deterministic backend validation and policy enforcement.

Refund mutating tools should update only the owning purchase detail table for the product type being processed:

* digital refund actions update `digital_purchase_details`
* physical refund actions update `physical_purchase_details`
* subscription refund actions update `subscription_purchase_details`

No tool should create or depend on a standalone `refunds` table.

Tools should not send database-derived refund deadlines. PostgreSQL triggers compute refund window fields from persisted purchase/detail state.

The current frontend help panel includes temporary manual `Prep Refund` and `Issue Refund` commands that call backend refund workflow endpoints through same-origin frontend proxy routes. These commands are not AI-callable tools. They exist to validate backend workflow state and frontend lifecycle displays before Phase 4 agent-triggered mutations.

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

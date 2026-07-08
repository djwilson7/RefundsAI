# 11-tools.md

# Tool Specifications

## Purpose

This document defines the language-model tool surface and chat orchestration contract.

Implementation source:

* Chat service: `apps/api/src/refunds_ai_api/services/ai_chat/service.py`
* Graph shape: `apps/api/src/refunds_ai_api/services/ai_chat/graph.py`
* Tools: `apps/api/src/refunds_ai_api/services/ai_chat/tools.py`
* Workflow routing: `apps/api/src/refunds_ai_api/services/ai_chat/workflows/`
* Resolver modules: `apps/api/src/refunds_ai_api/services/ai_chat/resolvers/`
* Refund mutation modules: `apps/api/src/refunds_ai_api/services/ai_chat/workflows/refund_mutation/`
* State normalization: `apps/api/src/refunds_ai_api/services/ai_chat/state.py`
* Prompt/context packaging: `apps/api/src/refunds_ai_api/services/ai_chat/prompts.py`
* Response guards: `apps/api/src/refunds_ai_api/services/ai_chat/responses.py`
* Trace formatting: `apps/api/src/refunds_ai_api/services/ai_chat/trace/`
* Compatibility trace entrypoint: `apps/api/src/refunds_ai_api/services/ai_chat/trace_formatting.py`
* Audit writer service: `apps/api/src/refunds_ai_api/services/audit.py`
* Audit repository: `apps/api/src/refunds_ai_api/repositories/audit.py`

## Tool Design Principles

* Tools provide authoritative backend information to the model.
* Tools should be deterministic and narrow.
* The active request supplies `customer_id`; the model must not choose or widen identity.
* OpenAI-facing tools are read-only in the current architecture.
* Refund mutations run through deterministic backend workflow execution after exact confirmation, not through model-selected write tools.
* Tool output should be safe for customer-facing explanation.

## Active OpenAI-Facing Tools

| Category | Tool | Purpose | Mutates state |
| --- | --- | --- | --- |
| Purchases | `get_customer_purchase_history` | Read active-customer purchase rows and aggregates. | No |
| Customers | `validate_customer_account` | Read active mock-customer metadata for the request customer id. | No |
| Purchases | `get_purchase_history_by_date_range` | Read purchases for an inclusive local date range. | No |
| Purchases | `get_purchase_count_by_amount_threshold` | Count purchases matching a cent-based threshold. | No |
| Policies | `get_refund_policy` | Read deterministic policy catalog sections. | No |
| Refunds | `get_refund_eligibility` | Read backend-evaluated refund workflow decisions. | No |

No OpenAI-facing tool may prepare, submit, issue, cancel, or otherwise mutate refund state.

## Chat Graph

Graph shape:

```text
validate_context
  -> request_tool_call
  -> execute_tools
  -> generate_final_response
```

The graph is intentionally small. Deterministic routing and context resolution happen
inside the execution path before a model-requested tool is honored.

## Deterministic Workflow Routing

Workflow routing is built from two resolved values:

1. Conversation object.
2. Requested operation.

Conversation objects include:

* `full_purchase_history`
* `active_result_set`
* `active_purchase`
* `page_purchase`
* `product_reference`
* `purchase_type`
* `date_range`
* `amount_threshold`
* `unknown`

Operations include:

* `count`
* `list`
* `select_first`
* `select_last`
* `select_latest`
* `select_previous`
* `policy`
* `eligibility`
* `start_refund`
* `explain`
* `unknown`

The lookup table maps object-operation pairs to workflow families:

* `account_fact`
* `refund_policy`
* `refund_eligibility`
* `refund_mutation`
* `off_domain`

This keeps the model from becoming the authority for purchase scope, policy scope, or
workflow target.

## Context Resolution Rules

The endpoint accepts compact page context:

* `surface: "purchase_history"`
* `surface: "purchase_detail"` plus `purchase_id`

It returns compact `conversation_state` for follow-up routing:

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
* `active_purchase`
* `active_workflow`
* `pending_refund_action`
* `customer_explanation_context`
* `entity_extraction_result`
* `current_page`

The model receives only compact context. The backend must not send full rendered page
content or replay the full transcript as a substitute for structured state.
`customer_explanation_context` is normalized by the backend for denied refund process
actions so the model can explain the exact customer-facing reason without relying on
raw workflow status, lock reason, or mutation terms.

Final-response model calls receive a request-specific projection of backend tool
results, not raw purchase-history payloads by default. The projection keeps backend
state references authoritative while sending only the rows, summaries, and eligibility
fields needed for the current request category. Compact purchase rows used for model
wording omit internal ids and order numbers unless that identifier is directly needed
for the customer-facing answer. Projection diagnostics record raw-context tokens,
projected-context tokens, estimated savings, request category, and projection reason
on model lifecycle audit events.

Response instructions are composed from small request-category modules. This keeps the
final-response prompt specific to count, list, policy, eligibility, confirmation,
execution, or fallback behavior without changing deterministic routing authority.

Resolution precedence:

1. Exact canonical refund confirmation command boundary.
2. Purchase id, order number, or SKU from the current message.
3. Named product from the current message, resolved against full purchase history.
4. Page purchase, then active purchase.
5. Singular or contextually selected purchase inside the active result set.
6. Purchase type, date range, or amount threshold from message text.
7. Full purchase history when a supported account-fact intent has no narrower target.
8. Clarification or off-domain response.

Explicit named product references override a narrowed selected set. The resolver uses
case-insensitive matching and accepts only unique, high-confidence fuzzy matches.
Demonstrative references such as "those purchases" resolve to the active result set
when one exists.

Entity extraction separates intent/action text from purchase entities. Product search
runs only for named products, purchase ids, order numbers, and SKUs. Pronouns,
determiners, action phrases, and generic support phrases are rejected as search terms
and resolve through `active_purchase`, page context, or a singular active result set.
When no named or contextual entity resolves, refund workflows ask for a product or
order identifier instead of widening to all purchases.

Workflow context audit events record `current_message_entity`,
`previous_context_scope`, `resolution_scope_used`, `match_candidates`,
`selected_purchase_id`, and `resolution_reason`. These fields show whether an active
result set was used or overridden without making audit metadata authoritative.

Each backend tool invocation has one lifecycle id shared by its start and completion
events. Timeline views may show both events, while Tool History and session metrics
merge them into one call. Tool totals count unique lifecycle ids; model totals count
unique model-call ids. Tool latency remains separate from model latency. Tool lifecycle
records expose estimated input/output token counts for the serialized deterministic
arguments and results so backend payload growth is visible, but backend tools add no
provider model tokens unless the tool itself invokes a model.

Each backend model invocation also emits a token-budget diagnostic log and stores the
same estimate on the model lifecycle audit event. It uses the pinned OpenAI `tiktoken`
package for the model encoding when available and a clearly labeled character
approximation only if tokenization fails. The report counts the exact assembled
messages and tool schemas by safe component category, including system/developer
prompts, current user message, conversation/workflow state, policy, customer and
purchase context, tool definitions, tool results, other messages, and the returned
model text. This diagnostic estimate does not replace provider-reported usage in
authoritative audit totals.

Refund confirmation-command prompts and successful refund mutation responses may be
deterministic backend-authored responses that intentionally skip a final model call.
Those response events record zero provider tokens plus estimated deterministic output
tokens and request-category/projection diagnostics. Provider token totals remain
limited to actual model calls.

## Active Result Sets and Ranking

Aggregate/list results can become the active scope for follow-ups. Examples:

* purchase type filters
* amount thresholds
* date ranges
* full purchase-history list results

`active_result_set` stores ids plus metadata. It should not store full purchase rows.

Ranking terms resolve inside the active selected set first:

| User phrasing | Sort meaning |
| --- | --- |
| `oldest`, `earliest`, `first` | Lowest `purchased_at`. |
| `latest`, `most recent`, `newest`, `last` | Highest `purchased_at`. |
| `cheapest` | Lowest `amount_cents`. |
| `most expensive` | Highest `amount_cents`. |

Ranking-only follow-ups are account-fact questions. They must not call refund policy or
eligibility tools unless the customer explicitly asks about refund policy, refundability,
eligibility, approval, cancellation rules, or the refund process.

## Tool Contracts

### `get_customer_purchase_history`

Purpose: Read one customer's purchase history and aggregate totals.

Inputs:

* none from the model; active request supplies `customer_id`

Outputs:

* sanitized purchase rows
* `history_summary` with total historical count plus refunded/non-refunded splits
* `history_summary.by_purchase_type` with total/refunded/non-refunded counts per type
* `history_summary.by_status` with total/refunded/non-refunded counts per status
* `aggregates` with non-refunded count and amount totals
* `aggregates.by_purchase_type` and `aggregates.by_status` for non-refunded totals
* cent values and display dollar strings

Rules:

* Count questions such as "how many purchases have I made" should answer from
  `history_summary`.
* Purchase-type count questions such as digital, physical, or subscription counts
  should answer from `history_summary.by_purchase_type`.
* When every purchase in the requested group is aligned on one refunded/non-refunded
  aspect, do not spell out the split or mention "completed"; state the count and list
  the product names when the model has the projected rows.
* Aggregate counts and spend totals exclude fully refunded purchases with
  `status = 'refunded'`.
* Purchases still in the refund process, such as `refund_pending`, remain included in
  aggregate counts and spend totals.

Errors:

* `CUSTOMER_NOT_FOUND`
* `DATABASE_NOT_CONFIGURED`

### `validate_customer_account`

Purpose: Read the active mock customer account supplied by the request.

Inputs:

* none from the model; active request supplies `customer_id`

Outputs:

* `customer_id`
* `valid`
* display and role metadata

Rules:

* This is a read-only mock-auth helper.
* The model must not provide, choose, or widen `customer_id`.
* Refund ownership remains a backend/database check against active-customer purchase rows.

### `get_purchase_history_by_date_range`

Purpose: Read purchase history for an inclusive local date range.

Inputs:

* `start_date` as `YYYY-MM-DD`
* `end_date` as `YYYY-MM-DD`
* `timezone`, such as `America/Chicago`

Outputs:

* resolved `date_range`
* sanitized purchase rows
* `history_summary` with total historical count plus refunded/non-refunded splits
* `aggregates` with non-refunded count and amount totals

Rules:

* Dates are interpreted in the customer timezone.
* Queries use a half-open timestamp range: start inclusive, day-after-end exclusive.
* Business weeks run Sunday through Saturday.
* Count answers should use `history_summary` when the customer asks how many
  purchases were made in the range.
* Aggregate counts and spend totals exclude fully refunded purchases with
  `status = 'refunded'`; refund-in-progress purchases remain included.

Errors:

* `CUSTOMER_NOT_FOUND`
* `DATABASE_NOT_CONFIGURED`

### `get_purchase_count_by_amount_threshold`

Purpose: Count purchases matching an amount threshold.

Inputs:

* `threshold_cents`
* `comparison`: `gt`, `gte`, `lt`, or `lte`

Outputs:

* `count`
* `matching_purchase_ids`
* `total_amount_cents`
* `total_amount_dollars`
* threshold and comparison metadata

Rules:

* User dollar amounts are converted to cents at the chat boundary.
* Comparisons run against `amount_cents`.
* Fully refunded purchases with `status = 'refunded'` are excluded from the count,
  matching ids, and total amount; refund-in-progress purchases remain included.

Errors:

* `CUSTOMER_NOT_FOUND`
* `DATABASE_NOT_CONFIGURED`

### `get_refund_policy`

Purpose: Read deterministic refund policy catalog sections.

Inputs:

* `scope`: `general`, `product_type`, `funds_release`, or `administrative_review`
* optional `purchase_type`: `digital`, `physical`, or `subscription`

Outputs:

* `scope`
* `purchase_type`
* `effective_date`
* `sections[]`
* `source`

Rules:

* Does not inspect customer purchases.
* Does not calculate eligibility.
* Does not mutate state.

Errors:

* none expected from the current in-memory catalog

### `get_refund_eligibility`

Purpose: Read backend-evaluated refund workflow state for backend-resolved purchase ids.

Inputs:

* `purchase_ids`
* `context`, such as `product`, `current_page`, `selected_set`, `date_range`, or `all_purchases`

Outputs:

* requested and resolved purchase ids
* counts by eligible, blocked, prepared, and issued state
* purchase rows with safe display fields
* workflow fields from `ApplicationService.get_refund_workflow`
* safe `policy_facts`

Rules:

* The backend filters requested ids against the active customer's purchases.
* The tool calls backend workflow policy for each purchase.
* The model may explain outcomes but must not prepare or issue refunds from this tool.

Errors:

* `CUSTOMER_NOT_FOUND`
* `DATABASE_NOT_CONFIGURED`

## Refund Process Mutation Gate

Refund process mutations execute only through backend services.

Required conditions:

* The resolver identifies exactly one purchase owned by the active customer.
* `active_refund_context` carries the expected command and mutation action.
* The backend confirmation validator deterministically matches the current user
  message to the expected canonical command.
* The validator persists exact consent facts before mutation execution.
* The mutation executor loads persisted confirmation and verifies grant, match,
  customer, purchase, expected command, unused scope, and current workflow state.
* Backend workflow state allows the requested atomic action.

Canonical commands:

| Type | Command | Backend action |
| --- | --- | --- |
| Digital | `Confirm invalidate code and issue refund` | Prepare, verify preparation, issue, verify issuance |
| Physical | `Confirm start return and issue label` | `request_refund` preparation path |
| Subscription | `Confirm cancel and issue refund` | Prepare, verify preparation, issue, verify issuance |

Prepared purchases that can issue funds may be confirmed through active refund context
for the issuance path. The backend still revalidates current workflow state before
calling `ApplicationService.issue_refund`.

For digital and subscription purchases, the first confirmed canonical command performs
that issuance path immediately after the preparation step verifies as persisted. For
physical purchases, the first confirmed command stops after return preparation because
fund issuance is gated by carrier acceptance.

For a single eligible physical purchase that requires a return label,
`pending_refund_action` is returned in compact conversation state with purchase id,
product name, purchase type, action, required action, and expected command. The
confirmation route may use that pending action as the target, but it must still call
the backend confirmation validator with the active request `customer_id` before any
refund mutation execution.

Generic replies such as `yes`, `proceed`, `go ahead`, `do it`, or `continue` do not
mutate state at the canonical-command boundary.

Declines and invalid commands do not mutate state.

The model is only the conversational surface for this flow. It may present the
canonical command and route the response, but it is not the consent authority.
Only the backend validator may set `refund_confirmation_granted = true`, and
refund mutation execution must not rely on raw chat text alone.

## Response Guards

Account-fact responses require authoritative tool data.

Refund policy explanations require `get_refund_policy`.

Refund eligibility explanations require `get_refund_eligibility`.

The assistant must not expose internal implementation terms in customer-facing text,
including:

* graph
* node
* tool
* resolver
* selected context
* selected set
* state
* purchase ids
* mutation
* backend step
* persisted state
* `issue_funds`
* `invalidate_code`
* `cancel_subscription`
* `required_action`

Customer-facing content should describe overall handling as "the refund process".
For physical return label and carrier steps, use "the return process".

## Tool Schema Exposure

The OpenAI-facing tool schema list is narrowed before each tool-selection model call.
Deterministic workflow classification controls the available schema set:

* account validation requests expose only `validate_customer_account`
* refund policy requests expose only `get_refund_policy`
* refund eligibility requests expose only `get_refund_eligibility`
* amount-threshold account facts expose only `get_purchase_count_by_amount_threshold`
* date-range account facts expose only `get_purchase_history_by_date_range`
* other account facts expose only `get_customer_purchase_history`
* off-domain, fallback, and refund mutation flows expose no read-only tools

When no OpenAI-facing tools are relevant, the graph skips the tool-selection model call
instead of sending an empty or irrelevant schema bundle. This optimization must not
change workflow classification, refund mutation behavior, or response wording.

## Logging and Trace Events

Chat logs should show the observable orchestration path without dumping full nested
prompts, tool payloads, or response objects.

Model audit persistence writes through the audit boundary:

| Component | Responsibility |
| --- | --- |
| `ModelAuditWriterService` | Starts sessions, appends ordered events, and completes or fails sessions. |
| `ModelAuditEventKey` | Defines stable event keys backed by `model_audit_event_lookup`. |
| `ModelAuditRepository` | Owns SQL writes for `model_audit_sessions` and `model_audit_events`. |

`/api/chat` starts an audit session for each valid chat request. When graph state
contains an audit session and writer, `log_trace_step` maps trace events to stable
audit keys and persists them in sequence. The route finalizes the session after
the response-returned trace event, including token usage reported by model calls
and computed latency.

Trace events should cover:

* route receipt
* graph start
* model request package
* workflow classification
* workflow context resolution
* tool selection and overrides
* invalid model output
* tool execution and results
* response blocking
* confirmation command generation and receipt
* refund mutation lifecycle summaries
* final response
* route return

Normal successful refund mutations should emit one grouped `workflow.refund_mutation_lifecycle`
block with purchase, confirmation, transition, validation, and final-result fields.
Error paths should still emit expanded diagnostics for authorization, policy, or
persistence failures.

Structured log records should retain event payloads for tests and future audit surfaces.
Console summaries should remain concise and human-readable.

## Tool Evolution

When adding or changing tools:

* Update `tools.py` schema and execution wrapper.
* Update workflow routing if the tool affects classification.
* Update response guards if customer-facing behavior changes.
* Update `09-api.md` if request/response state changes.
* Update tests in `apps/api/tests/ai_chat/`.
* Preserve read-only OpenAI-facing tools unless a decision explicitly changes the architecture.

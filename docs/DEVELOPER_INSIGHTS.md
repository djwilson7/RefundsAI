# Developer Insights

## Purpose

This document captures engineering reasoning and implementation tradeoffs.

It is not the authoritative source for project rules. Those live in `.ai-context/`.
This file explains why the project evolved the way it did.

## Current Project State

The core technical challenge is complete through text chat orchestration,
confirmation-gated refund execution, and administrative auditability.

## Insight 001 - Context Before Code

The project established `.ai-context/` before implementation work.

Reason:

* The technical challenge needs a coherent architecture, not a disposable prototype.
* AI agents and human contributors need the same source of truth.
* Clear context reduces architecture drift and model-generated scope creep.

Tradeoff:

* Initial coding starts later.
* Later implementation moves faster because the boundaries are already explicit.

## Insight 002 - Agent Behavior First

The primary evaluation target is the AI support workflow.

The project prioritizes:

* policy-governed refund decisions
* backend tool orchestration
* edge-case denial behavior
* trace visibility
* audit-ready execution paths

Reason:

The walkthrough should demonstrate an agent that can answer, explain, and safely guide
refund workflows. The UI supports that proof, but the agent workflow is the core product
claim.

## Insight 003 - Local-First Development

RefundsAI is optimized for local development before deployment.

Reason:

The technical challenge requires a GitHub repository, README, and walkthrough. Local
reproducibility matters more than hosted infrastructure during the early milestones.

Tradeoff:

A hosted demo can be added later, but deployment should not block the core agent and
refund workflow.

## Insight 004 - Refund State Belongs With Purchase Details

Refund state is embedded in product-type-specific detail tables:

* `digital_purchase_details`
* `physical_purchase_details`
* `subscription_purchase_details`

Reason:

Digital, physical, and subscription purchases have different refund-blocking facts.
A redeemed digital code, physical carrier acceptance event, and subscription proration
state should not be forced into one generic refund model.

Keeping state with the purchase detail owner:

* avoids duplicated lifecycle state
* keeps SQL ownership clear
* simplifies policy evaluation
* lets backend services and AI tools consume the same facts

Tradeoff:

Policy reads must load `purchases` and then the matching detail table. That is acceptable
because `purchases.purchase_type` already determines the authoritative detail table.

Database triggers also derive refund deadlines from persisted state. This prevents
clients from spoofing deadline values and keeps services focused on commands and event
facts.

## Insight 005 - Deterministic Policy Before API Wrappers

Core refund behavior lives in reusable policy and service functions before it is exposed
through HTTP.

Reason:

The same refund decisions must serve:

* REST endpoints
* frontend workflow controls
* AI tools
* chat-triggered workflow execution

Routes should stay thin: load request inputs, call services, and return standardized
response shapes.

Tradeoff:

The service layer adds structure early, but it makes refund behavior testable outside
HTTP and prepares the same deterministic logic for agent orchestration.

## Insight 006 - Frontend Detail Pages Present Backend State

Purchase detail pages use one stable route:

```text
/purchase-details/[purchaseId]
```

The backend resolves type-specific data through:

```text
GET /api/purchases/{purchase_id}/details
```

Reason:

The customer experience needs different sections for digital codes, physical delivery,
and subscription billing. The backend still owns which detail table applies and what
state is true.

For subscriptions:

* Billing cycle state lives under `Billing Cycle Details`.
* Prepared and issued refund state lives under `Return Details`.
* Prepared subscriptions show auto-renewal off, days used, and `Subscription Cancelled`.
* Issued subscription refunds add cancel date, amount, and the expected refund window.

Tradeoff:

The page has component branching, but avoids route proliferation and keeps frontend
presentation aligned with the API contract used by the agent.

## Insight 007 - Manual Refund Commands Before Agent Orchestration

The help panel previously exposed temporary manual commands on purchase detail pages:

* `Prep Refund`
* `Issue Refund`

They were disabled by default and enabled only from backend workflow flags:

* `can_prepare_refund`
* `can_issue_funds`

Reason:

These commands let the project validate the full refund path before relying on AI chat:

* same-origin frontend proxy routes
* FastAPI refund endpoints
* guarded backend mutations
* route refresh behavior
* prepared and issued state displays

Physical returns also include a detail-page `Given to Carrier` command because carrier
acceptance is a product-specific lifecycle event shown in the return workflow display.

Outcome:

Manual commands were useful for integration testing, but they are no longer the product
interaction model. The current experience is chat-owned refund initiation and issuance,
with exact backend confirmation gates. Detail pages continue to display backend state
and retain the physical carrier-acceptance control for local workflow validation.

## Insight 008 - Deterministic Chat Context Before Model Prose

The chat workflow resolves each message into a conversation object and operation before
selecting a workflow.

Objects include:

* product references
* active result sets
* purchase types
* date ranges
* amount thresholds
* page purchases
* active purchases
* full purchase history

Reason:

Follow-ups like "list them", "what's the first one?", and "what is the policy for these
types of products?" are easy to over-broaden if the model sees raw full-history context.
The backend already knows the selected scope, so it should represent that scope
explicitly.

Implementation detail:

`conversation_state.active_result_set` stays compact and ID-only. The final-response
request hydrates safe display fields only when that filtered set is the primary answer
source.

Tradeoff:

There are more resolver modules and trace summaries, but responsibilities are clearer:

* backend code owns scope resolution
* tools own authoritative data retrieval
* the model owns wording from provided sources

## Insight 009 - Refund Mutations Need a Canonical Confirmation Gate

AI chat can help begin or close out a refund workflow, but mutation remains backend-owned.

Reason:

The model should not decide whether money movement or lifecycle mutation happens.
The backend must resolve one concrete purchase, validate workflow permission, and require
an exact customer confirmation command before any write occurs.

Current command boundary:

* Eligibility can store compact `active_refund_context`.
* The assistant gives a product-specific canonical command.
* A later customer turn must match that command after deterministic normalization.
* Backend code creates internal pending action state and calls `ApplicationService`.
* Generic replies such as `yes`, `proceed`, or `do it` do not mutate state at this boundary.

Tradeoff:

This adds one explicit confirmation step, but it prevents accidental writes from broad
follow-ups, stale selected state, or ambiguous language.

It also gives logs a clean audit boundary:

* confirmation command generated
* confirmation received or rejected
* mutation attempted
* conflict or completion recorded

## Insight 010 - Agentic Does Not Mean Model-Controlled

The finished workflow is deliberately hybrid:

* Models interpret language, request narrow read tools, and explain grounded results.
* Deterministic code resolves authority, validates consent, and executes mutations.
* Exact confirmation turns can complete with zero model calls.

This avoids adding cost and uncertainty after the customer and backend have agreed on
one authorized action.

## Insight 011 - Audit Evidence And Presentation Serve Different Audiences

The database keeps every ordered event and raw payload. The admin UI translates those
facts into narrative titles, readable metadata, and tool-purpose descriptions.

This preserves technical evidence without requiring reviewers to decode internal trace
names. Provider tokens remain separate from estimated backend payload tokens.

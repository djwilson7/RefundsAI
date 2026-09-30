# 05-standards.md

# Engineering Standards

## General Principles

* Prefer clear, explicit behavior over clever inference.
* Keep files focused on one responsibility.
* Reuse local patterns before introducing abstractions.
* Preserve frontend, route, service, repository, policy, and database ownership boundaries.
* Keep business decisions deterministic and testable.
* Update documentation with behavior changes.

## Frontend Standards

Implementation surface: `apps/web`.

For containerized frontend-only development, use `docker-compose.dev.yml`. It provides
source bind mounts and polling-based hot reload without starting FastAPI. Keep the
standard `docker-compose.yml` aligned with the integrated production-style build.

Use the existing patterns:

* Server components load backend data for page-level reads.
* Client components own browser interaction, transient UI state, and session-storage hints.
* Same-origin route handlers proxy browser calls to FastAPI.
* `apps/web/src/lib/application-api.ts` maps backend snake_case API payloads into frontend camelCase types.
* CSS modules own component styling.
* Global CSS owns application baseline styling.
* Shared icon-button primitives live in the root stylesheet's `components` cascade
  layer. Component themes remain in CSS modules and override that layer, so route
  stylesheet load order cannot reset icon sizes, colors, or surfaces.

Do not:

* Make frontend state authoritative for identity, purchase, refund, or policy data.
* Reimplement backend policy in components.
* Add direct Supabase or OpenAI calls from frontend code.
* Use inline styles for normal component styling.

## Backend Standards

Implementation surface: `apps/api`.

Use the existing route/service/repository split:

| Layer | Standard |
| --- | --- |
| Routes | Validate request shape, call services, map known exceptions to `ApiResponse`. |
| Services | Coordinate business workflows and deterministic policy. |
| Repositories | Isolate SQL and transaction behavior. |
| Policy helpers | Return pure deterministic decisions from persisted facts. |
| Schemas | Define frontend-facing response shape with Pydantic. |

Routes should stay thin. Business logic belongs in services and policy helpers.

Repository mutations that change refund state should guard expected persisted state and
raise conflicts when the write does not apply exactly once.

## AI Chat Standards

Implementation surface: `apps/api/src/refunds_ai_api/services/ai_chat`.

Chat behavior should remain modular:

* `graph.py` defines the small LangGraph shape.
* `nodes/` define graph nodes.
* `workflows/` resolve object, operation, workflow kind, and workflow context.
* `workflows/tool_routing.py`, `workflows/tool_execution.py`, and
  `workflows/state_updates.py` keep deterministic tool flow focused.
* `workflows/refund_mutation/` owns confirmation-gated refund mutation behavior.
* `resolvers/` owns page, product, purchase, policy, eligibility, and account-fact resolution.
* `trace/` owns structured trace summaries and readable trace block formatting.
* `tools.py` defines read-only OpenAI-facing tool schemas and backend execution wrappers.
* `state.py` normalizes compact client-carried state.
* `prompts.py` builds system and compact model-context messages.
* `responses.py` guards customer-facing text.

OpenAI-facing tools should be read-only unless the architecture is explicitly changed.
Refund mutations should continue through deterministic backend confirmation gates.
Do not add a model call to a canonical confirmation path merely to rewrite an already
verified transactional result.

## Database Standards

Implementation surface:

* `apps/api/src/refunds_ai_api/database/migrations/`
* `apps/api/src/refunds_ai_api/database/migrator.py`
* `apps/api/src/refunds_ai_api/database/seeds.py`

Every business table migration should define:

* Primary key and foreign keys.
* Check and uniqueness constraints.
* Query indexes.
* Row-level security enablement.
* Backend-only RLS policy where frontend/database direct access remains out of scope.

Derived refund deadline/default fields should remain database-managed when they depend
on persisted table state.

## Naming

Use names that match the domain:

* `purchase_type` for digital, physical, subscription.
* `refund_stage` for blocked, eligible, prepared, issued.
* `required_action` for the next backend workflow action.
* `policy_facts` for backend-selected facts exposed with a workflow decision.

Avoid ambiguous names such as `eligible` when the field is really a workflow gate like
`can_prepare_refund` or `can_issue_funds`.

## Documentation

Documentation should be compact and implementation-grounded.

Prefer:

* Short sections.
* Tables for contracts.
* Source file references.
* Focused explanation of why a boundary exists.

Avoid:

* Long dense paragraphs that mix architecture, API payloads, and business rules.
* Repeating the same authority statement in every document.
* Generic product claims that are not backed by implemented code.

Final project documentation should lead with the bounded-agent architecture and clearly
separate model behavior, deterministic backend behavior, provider token usage, and
estimated backend payload metrics.

## Audit Presentation

Admin audit presentation may translate stored trace fields into audience-readable
labels and narrative summaries, but it must:

* Preserve every persisted event and its original sequence number.
* Keep raw payloads available for technical inspection.
* Distinguish event type, lifecycle status, workflow, operation, and token provenance.
* Describe tool purpose separately from the recorded outcome of one invocation.

## Validation

Run the smallest meaningful validation first:

* Backend route/service/policy changes: targeted pytest.
* Frontend component or API mapping changes: targeted Vitest.
* Docs-only changes: inspect Markdown structure and run text searches for stale terms.

Use broader test runs when behavior crosses route, service, repository, database, and
frontend boundaries.

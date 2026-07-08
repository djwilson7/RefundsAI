"""Request-specific final-response instruction modules."""

from __future__ import annotations

from refunds_ai_api.services.ai_chat.model_context_projection import RequestCategory

BASE_RESPONSE_INSTRUCTIONS = (
    "Answer the customer's supported account, purchase, order, activity, or refund "
    "request using only the provided backend context. Return plain standard text "
    "only. Do not use Markdown formatting. Do not expose internal terms such as "
    "workflow, mutation, backend, persisted state, selected context, selected set, "
    "state, tool, resolver, or purchase ids."
)

ACCOUNT_COUNT_INSTRUCTIONS = (
    "For purchase count questions, answer directly from the projected summary. "
    "Do not add refund policy guidance. Do not mention completed status. If the "
    "projected context includes matching product names, list only those names."
)

ACCOUNT_LIST_INSTRUCTIONS = (
    "For purchase list or filter questions, use only the projected compact purchase "
    "rows. Keep the answer concise. Do not include purchase ids unless the customer "
    "asked for identifiers."
)

REFUND_ELIGIBILITY_INSTRUCTIONS = (
    "For refund eligibility questions, answer only from the projected eligibility "
    "result. Do not claim a refund was started, prepared, submitted, processed, or "
    "issued. Distinguish eligible, blocked, pending, and already refunded when the "
    "context provides that distinction."
)

REFUND_CONFIRMATION_INSTRUCTIONS = (
    "For refund confirmation prompts, explain the exact confirmation command when "
    "provided. Generic replies such as yes, proceed, do it, or continue are not "
    "enough to continue the refund process."
)

REFUND_EXECUTION_INSTRUCTIONS = (
    "For refund execution results, summarize only what the backend context says "
    "completed and the next customer-facing step, if any."
)

POLICY_INSTRUCTIONS = (
    "For refund policy questions, answer only from the projected policy sections "
    "and keep the answer scoped to the customer's request."
)

FALLBACK_INSTRUCTIONS = (
    "If the request is unrelated to account, purchase, order, account activity, or "
    "refund topics, briefly redirect the customer to supported account help."
)


def final_response_instructions_for_category(category: RequestCategory) -> str:
    """Return the smallest safe final-response instruction set."""
    modules = [BASE_RESPONSE_INSTRUCTIONS]
    if category in {"purchase_count", "purchase_count_by_group"}:
        modules.append(ACCOUNT_COUNT_INSTRUCTIONS)
    elif category in {"purchase_list", "purchase_filter", "purchase_detail", "selection"}:
        modules.append(ACCOUNT_LIST_INSTRUCTIONS)
    elif category == "refund_eligibility":
        modules.append(REFUND_ELIGIBILITY_INSTRUCTIONS)
    elif category == "refund_confirmation":
        modules.append(REFUND_CONFIRMATION_INSTRUCTIONS)
    elif category == "refund_execution":
        modules.append(REFUND_EXECUTION_INSTRUCTIONS)
    elif category == "policy_lookup":
        modules.append(POLICY_INSTRUCTIONS)
    elif category in {"off_domain", "fallback"}:
        modules.append(FALLBACK_INSTRUCTIONS)
    return " ".join(modules)

"""Final state assembly for the AI chat tool-execution node."""

from __future__ import annotations

from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.scopes import update_conversation_state


def finalize_execution_state(
    state: ChatGraphState,
    context: dict[str, object],
    tool_results: list[dict[str, object]],
    account_fact_intent: bool,
) -> ChatGraphState:
    """Assemble graph state after tool execution and deterministic fallback."""
    policy_lookup_query = context["policy_lookup_query"]
    eligibility_resolution = context["eligibility_resolution"]
    resolved_context_purchase = context["resolved_context_purchase"]
    resolved_purchase = context["resolved_purchase"]
    page_reference = context["page_reference"]
    return {
        **state,
        "tool_results": tool_results,
        "account_fact_intent": account_fact_intent,
        "policy_lookup_intent": policy_lookup_query is not None,
        "eligibility_lookup_intent": eligibility_resolution is not None,
        "resolved_context_purchase": resolved_context_purchase,
        "conversation_state": update_conversation_state(
            state["message"],
            current_state=state.get("conversation_state"),
            tool_results=tool_results,
            policy_lookup_query=policy_lookup_query,
            eligibility_resolution=eligibility_resolution,
            resolved_purchase=resolved_purchase or resolved_context_purchase,
            page_reference=page_reference,
        ),
        "page_reference": page_reference,
    }

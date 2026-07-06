"""Resolved execution context for the AI chat tool-execution node."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_date_range_query
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.parsing import parse_amount_threshold_query
from refunds_ai_api.services.ai_chat.resolution import (
    resolve_page_reference,
    resolve_refund_policy_query_with_purchase,
)
from refunds_ai_api.services.ai_chat.workflow import (
    parse_refund_workflow_continuation_intent,
)


def resolve_execution_context(runtime: Any, state: ChatGraphState) -> dict[str, Any]:
    """Build resolved context needed by tool execution and fallback routing."""
    customer_id = state["customer_id"]
    threshold_query = parse_amount_threshold_query(state["message"])
    date_range_query = parse_date_range_query(state["message"])
    (
        policy_lookup_query,
        resolved_purchase,
        unresolved_product_reference,
    ) = resolve_refund_policy_query_with_purchase(
        state["message"],
        conversation_state=state.get("conversation_state"),
        page_context=state.get("page_context"),
        application_service=runtime.application_service,
        customer_id=customer_id,
    )
    page_reference = resolve_page_reference(
        runtime.application_service,
        customer_id,
        state.get("page_context"),
    )
    workflow_continuation_intent = parse_refund_workflow_continuation_intent(
        state["message"]
    )
    return {
        "customer_id": customer_id,
        "threshold_query": threshold_query,
        "date_range_query": date_range_query,
        "policy_lookup_query": policy_lookup_query,
        "resolved_purchase": resolved_purchase,
        "unresolved_product_reference": unresolved_product_reference,
        "page_reference": page_reference,
        "workflow_continuation_intent": workflow_continuation_intent,
    }

"""Context-validation graph node for AI chat."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.resolution import resolve_refund_policy_query
from refunds_ai_api.services.ai_chat.responses import (
    CHAT_UNAVAILABLE_RESPONSE,
    CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
)
from refunds_ai_api.services.ai_chat.routing import has_refund_eligibility_intent
from refunds_ai_api.services.ai_chat.workflow import parse_refund_workflow_mutation_intent


def validate_context_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    state = log_trace_step(
        state,
        message="LangGraph chat workflow started.",
        event_type="graph.started",
        data={
            "customer_id": state.get("customer_id"),
            "purchase_id": state.get("purchase_id"),
            "page_context": state.get("page_context"),
            "model": runtime.model,
        },
    )

    policy_lookup_query = resolve_refund_policy_query(
        state["message"],
        conversation_state=state.get("conversation_state"),
        page_context=state.get("page_context"),
    )
    eligibility_intent = has_refund_eligibility_intent(
        state["message"],
        conversation_state=state.get("conversation_state"),
    )
    blocked_intent = parse_refund_workflow_mutation_intent(state["message"])

    if (
        not state.get("customer_id")
        and policy_lookup_query is None
        and blocked_intent is None
        and not eligibility_intent
    ):
        state = log_trace_step(
            state,
            message="Stopped before model call because no customer context was supplied.",
            event_type="graph.stopped",
            data={"reason": "customer_context_required"},
        )
        return {
            **state,
            "assistant_response": CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
            "error": "customer_context_required",
        }

    if not state.get("customer_id") and eligibility_intent:
        state = log_trace_step(
            state,
            message=(
                "Stopped before eligibility lookup because no customer "
                "context was supplied."
            ),
            event_type="graph.stopped",
            data={"reason": "customer_context_required"},
        )
        return {
            **state,
            "assistant_response": CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
            "error": "customer_context_required",
        }

    if runtime.model_client is None:
        state = log_trace_step(
            state,
            message="Stopped before model call because OPENAI_API_KEY is not configured.",
            event_type="model.failure",
            level=logging.WARNING,
            data={"reason": "missing_openai_api_key", "model": runtime.model},
        )
        return {
            **state,
            "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
            "error": "missing_openai_api_key",
        }

    return state

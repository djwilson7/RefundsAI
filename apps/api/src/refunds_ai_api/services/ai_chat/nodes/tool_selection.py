"""Tool-selection graph node for AI chat."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from refunds_ai_api.services.ai_chat.audit_instrumentation import merge_token_usage
from refunds_ai_api.services.ai_chat.logging import (
    build_model_context_summary,
    log_trace_step,
)
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.parsing import has_invalid_pseudo_tool_output
from refunds_ai_api.services.ai_chat.prompts import (
    SYSTEM_PROMPT,
    build_compact_model_context_message,
)
from refunds_ai_api.services.ai_chat.responses import CHAT_UNAVAILABLE_RESPONSE
from refunds_ai_api.services.ai_chat.routing import has_account_fact_intent
from refunds_ai_api.services.ai_chat.tools import (
    get_customer_purchase_history_tool_schema,
    get_purchase_count_by_amount_threshold_tool_schema,
    get_purchase_history_by_date_range_tool_schema,
    get_refund_eligibility_tool_schema,
    get_refund_policy_tool_schema,
    validate_customer_account_tool_schema,
)


def request_tool_call_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    account_fact_intent = has_account_fact_intent(state["message"])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": state["message"]},
    ]
    compact_context_message = build_compact_model_context_message(state)
    if compact_context_message is not None:
        messages.append(compact_context_message)
    tools = [
        validate_customer_account_tool_schema(),
        get_customer_purchase_history_tool_schema(),
        get_purchase_count_by_amount_threshold_tool_schema(),
        get_purchase_history_by_date_range_tool_schema(),
        get_refund_policy_tool_schema(),
        get_refund_eligibility_tool_schema(),
    ]
    model_call_id = str(uuid4())
    model_started_at = datetime.now(UTC)
    model_started = perf_counter()
    state = log_trace_step(
        {**state, "account_fact_intent": account_fact_intent},
        message="Sending tool-selection package to the model.",
        event_type="model.requested",
        data={
            "phase": "tool_selection",
            "model": runtime.model,
            "model_call_id": model_call_id,
            "started_at": model_started_at.isoformat(),
            "messages": messages,
            "tools": tools,
            "model_context": build_model_context_summary(state),
        },
    )

    try:
        turn = runtime.model_client.generate(messages=messages, tools=tools)
    except Exception as exc:
        model_completed_at = datetime.now(UTC)
        state = log_trace_step(
            state,
            message="Model tool-selection request failed.",
            event_type="model.failure",
            level=logging.WARNING,
            data={
                "reason": exc.__class__.__name__,
                "detail": str(exc),
                "model": runtime.model,
                "model_call_id": model_call_id,
                "phase": "tool_selection",
                "status": "failed",
                "started_at": model_started_at.isoformat(),
                "completed_at": model_completed_at.isoformat(),
                "latency_ms": max(
                    0,
                    round((perf_counter() - model_started) * 1000),
                ),
            },
        )
        return {
            **state,
            "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
            "error": "model_request_failed",
        }

    model_completed_at = datetime.now(UTC)
    state = log_trace_step(
        state,
        message="Model tool-selection call completed.",
        event_type="model.completed",
        data={
            "model_call_id": model_call_id,
            "model": runtime.model,
            "phase": "tool_selection",
            "status": "completed",
            "started_at": model_started_at.isoformat(),
            "completed_at": model_completed_at.isoformat(),
            "latency_ms": max(0, round((perf_counter() - model_started) * 1000)),
            "prompt_tokens": (
                turn.token_usage.prompt_tokens if turn.token_usage is not None else None
            ),
            "completion_tokens": (
                turn.token_usage.completion_tokens
                if turn.token_usage is not None
                else None
            ),
            "reasoning_tokens": (
                turn.token_usage.reasoning_tokens
                if turn.token_usage is not None
                else None
            ),
            "total_tokens": (
                turn.token_usage.total_tokens if turn.token_usage is not None else None
            ),
            "workflow": state.get("workflow_kind"),
            "available_tools_count": len(tools),
            "tool_results_provided": 0,
            "conversation_state_summary": build_model_context_summary(state),
        },
    )
    state = log_trace_step(
        state,
        message="Model returned tool-call selection.",
        event_type="tool_call.requested",
        data={
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                for tool_call in turn.tool_calls
            ],
            "model_content": turn.content,
        },
    )
    invalid_model_output = has_invalid_pseudo_tool_output(turn.content)
    if invalid_model_output:
        state = log_trace_step(
            state,
            message="Model returned malformed pseudo-tool text instead of a tool call.",
            event_type="model.invalid_tool_output",
            data={"model_content": turn.content},
        )

    return {
        **state,
        "tool_calls": turn.tool_calls,
        "account_fact_intent": account_fact_intent,
        "invalid_model_output": invalid_model_output,
        "audit_token_usage": merge_token_usage(
            state.get("audit_token_usage"),
            turn.token_usage,
        ),
    }

"""Final-response graph node for AI chat."""

from __future__ import annotations

import json
import logging
from typing import Any

from refunds_ai_api.services.ai_chat.logging import (
    build_model_context_summary,
    log_trace_step,
    logger,
)
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.prompts import (
    SYSTEM_PROMPT,
    build_compact_model_context_message,
)
from refunds_ai_api.services.ai_chat.responses import (
    ACCOUNT_DATA_REQUIRED_RESPONSE,
    CHAT_UNAVAILABLE_RESPONSE,
    sanitize_customer_response,
)


def generate_final_response_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    if state.get("assistant_response"):
        return state

    tool_results = state.get("tool_results", [])
    if state.get("account_fact_intent") and not tool_results:
        state = log_trace_step(
            state,
            message=(
                "Blocked factual account response because no authoritative "
                "tool result exists."
            ),
            event_type="response.blocked",
            data={"reason": "account_fact_without_tool_result"},
            level=logging.WARNING,
        )
        return {**state, "assistant_response": ACCOUNT_DATA_REQUIRED_RESPONSE}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": state["message"]},
    ]
    compact_context_message = build_compact_model_context_message(
        state,
        tool_results=tool_results,
        page_reference=state.get("page_reference"),
    )
    if compact_context_message is not None:
        messages.append(compact_context_message)
    resolved_context_purchase = state.get("resolved_context_purchase")
    if resolved_context_purchase is not None:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Backend-resolved purchase context: "
                    f"{json.dumps(resolved_context_purchase, default=str)}"
                ),
            }
        )
    if tool_results:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Read-only account tool result: "
                    f"{json.dumps(tool_results, default=str)}"
                ),
            }
        )
    page_reference = state.get("page_reference")
    if page_reference:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Current page reference: "
                    f"{json.dumps(page_reference, default=str)}"
                ),
            }
        )

    messages.append(
        {
            "role": "user",
            "content": (
                "Answer the customer's request if it is about their account, "
                "account history, purchases, orders, account activity, or "
                "refund flows. Use the tool result when relevant. When the "
                "backend provides resolved purchase context, use that concrete "
                "purchase before ranking or selecting from broader purchase "
                "history. If the customer asks a ranking follow-up without "
                "refund, return, policy, eligibility, approval, or process "
                "wording, answer only the purchase fact requested and do not "
                "discuss refund policy. Do not expose backend terms such as "
                "selected context, selected set, state, tool, resolver, or "
                "purchase ids. For refund "
                "policy questions, answer only from the refund-policy tool "
                "result and keep the answer scoped to the customer's request. "
                "For refund eligibility questions, answer only from the "
                "refund-eligibility tool result and do not offer to start, "
                "prepare, issue, submit, or process a refund. "
                "If the request is unrelated, briefly redirect the customer "
                "back to supported account topics. Return plain standard text "
                "only, with no Markdown formatting."
            ),
        },
    )
    tools: list[dict[str, Any]] = []
    state = log_trace_step(
        state,
        message="Sending final-response package to the model.",
        event_type="model.requested",
        data={
            "phase": "final_response",
            "model": runtime.model,
            "messages": messages,
            "tools": tools,
            "model_context": build_model_context_summary(
                state,
                tool_results=tool_results,
                page_reference=page_reference,
            ),
        },
    )

    try:
        turn = runtime.model_client.generate(messages=messages, tools=tools)
    except Exception as exc:
        logger.warning(
            "ai.chat.model_failed: %s",
            exc,
            extra={
                "event": {
                    "type": "model.failure",
                    "reason": exc.__class__.__name__,
                    "detail": str(exc),
                    "model": runtime.model,
                }
            },
        )
        return {
            **state,
            "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
            "error": "final_model_request_failed",
        }

    assistant_response = sanitize_customer_response(
        turn.content or CHAT_UNAVAILABLE_RESPONSE,
        state,
    )
    state = log_trace_step(
        state,
        message="Model generated final assistant response.",
        event_type="response.generated",
        data={
            "model": runtime.model,
            "graph_ready": True,
            "tool_result_count": len(state.get("tool_results", [])),
            "assistant_response": assistant_response,
            "follow_up_tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                for tool_call in turn.tool_calls
            ],
        },
    )

    return {**state, "assistant_response": assistant_response}

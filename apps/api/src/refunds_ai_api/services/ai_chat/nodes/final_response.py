"""Final-response graph node for AI chat."""

from __future__ import annotations

import json
import logging
from typing import Any

from refunds_ai_api.services.ai_chat.audit_instrumentation import merge_token_usage
from refunds_ai_api.services.ai_chat.logging import (
    build_model_context_summary,
    log_trace_step,
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
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflow import (
    build_refund_confirmation_command_offer,
    normalize_refund_confirmation_command,
)


def generate_final_response_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    if state.get("assistant_response"):
        return state

    from refunds_ai_api.services.ai_chat.state import validate_context_integrity
    conv_state = state.get("conversation_state") or {}
    validated_state = validate_context_integrity(
        runtime.application_service,
        state.get("customer_id") or state.get("effective_customer_id"),
        conv_state,
        state.get("page_context")
    )
    state["conversation_state"] = validated_state

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

    empty_eligibility_result = _empty_refund_eligibility_result(tool_results)
    if empty_eligibility_result is not None:
        state = log_trace_step(
            state,
            message=(
                "Blocked final refund eligibility response because no purchase "
                "was evaluated."
            ),
            event_type="response.blocked",
            data={
                "reason": "empty_refund_eligibility_result_guardrail",
                "result": empty_eligibility_result,
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "assistant_response": (
                "I could not determine which purchase to check. Please choose "
                "one purchase by product name or order number."
            ),
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": state["message"]},
    ]
    compact_context_message = build_compact_model_context_message(
        state,
        tool_results=tool_results,
        page_reference=state.get("page_reference"),
        application_service=runtime.application_service,
    )
    if compact_context_message is not None:
        messages.append(compact_context_message)
    state = _log_refund_confirmation_command_generated(state, tool_results)
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
        raw_tool_result_label = (
            "Read-only account tool result: Raw trace/debug only. If "
            "deterministic response context sets primary_answer_source to "
            "active_result_set, do not broaden your answer to these raw results: "
        )
        conversation_state = state.get("conversation_state")
        if not (
            isinstance(conversation_state, dict)
            and isinstance(conversation_state.get("active_result_set"), dict)
        ):
            raw_tool_result_label = "Read-only account tool result: "
        messages.append(
            {
                "role": "user",
                "content": raw_tool_result_label
                + f"{json.dumps(tool_results, default=str)}",
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
                "history. If deterministic response context says "
                "primary_answer_source is active_result_set, answer only from "
                "active_result_set and do not broaden the answer to the full raw "
                "tool result. Use the active result set label when describing "
                "that scoped result. If the customer asks a ranking follow-up without "
                "refund, return, policy, eligibility, approval, or process "
                "wording, answer only the purchase fact requested and do not "
                "discuss refund policy. Do not expose internal terms such as "
                "workflow, mutation, backend, backend step, persisted state, "
                "orchestration, issue_funds, invalidate_code, "
                "cancel_subscription, required_action, selected context, "
                "selected set, state, tool, resolver, or purchase ids. Refer "
                "to refund handling as the refund process, and refer to "
                "return-label or carrier handling for physical purchases as "
                "the return process. For refund "
                "policy questions, answer only from the refund-policy tool "
                "result and keep the answer scoped to the customer's request. "
                "For refund eligibility questions, answer only from the "
                "refund-eligibility tool result and do not claim a refund was "
                "started, prepared, issued, submitted, or processed. If "
                "get_refund_eligibility evaluated zero purchases, do not say a "
                "purchase is eligible or ineligible; say the check could not be "
                "completed and ask for a product name or order number. Do not "
                "invent blocked reasons or infer denial from an empty item list. "
                "Distinguish not eligible, already refunded, refund pending, not "
                "evaluated, needs confirmation, and completed. If deterministic "
                "context includes a confirmation_command, explain what the "
                "command will do and include that exact command before anything "
                "changes. Generic replies "
                "such as yes, proceed, do it, or continue are not enough to "
                "continue the refund process. "
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
        state = log_trace_step(
            state,
            message="Final model response request failed.",
            event_type="model.failure",
            level=logging.WARNING,
            data={
                "reason": exc.__class__.__name__,
                "detail": str(exc),
                "model": runtime.model,
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
    assistant_response = _append_refund_confirmation_command_offer(
        assistant_response,
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

    return {
        **state,
        "assistant_response": assistant_response,
        "audit_token_usage": merge_token_usage(
            state.get("audit_token_usage"),
            turn.token_usage,
        ),
    }


def _empty_refund_eligibility_result(
    tool_results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for tool_result in reversed(tool_results):
        if not isinstance(tool_result, dict):
            continue
        if tool_result.get("name") != "get_refund_eligibility":
            continue
        result = tool_result.get("result")
        if isinstance(result, dict) and result.get("purchase_count") == 0:
            return result
    return None


def _append_refund_confirmation_command_offer(
    assistant_response: str,
    state: ChatGraphState,
) -> str:
    """Ensure eligible refund answers include the canonical mutation command."""
    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    active_refund_context = conversation_state.get("active_refund_context")
    if not isinstance(active_refund_context, dict):
        return assistant_response
    if active_refund_context.get("eligible") is not True:
        return assistant_response
    if active_refund_context.get("stage") not in {
        "eligibility_confirmed",
        "awaiting_return_label",
    }:
        return assistant_response
    command = active_refund_context.get("confirmation_command")
    if not isinstance(command, str) or not command:
        return assistant_response
    normalized_response = normalize_refund_confirmation_command(assistant_response)
    normalized_command = normalize_refund_confirmation_command(command)
    if normalized_command and normalized_command in normalized_response:
        return assistant_response
    offer = build_refund_confirmation_command_offer(active_refund_context)
    if not offer:
        return assistant_response
    return f"{assistant_response}\n\n{offer}"


def _log_refund_confirmation_command_generated(
    state: ChatGraphState,
    tool_results: list[dict[str, Any]],
) -> ChatGraphState:
    """Log canonical command generation after a single eligible result."""
    if not any(
        isinstance(tool_result, dict)
        and tool_result.get("name") == "get_refund_eligibility"
        for tool_result in tool_results
    ):
        return state
    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    active_refund_context = conversation_state.get("active_refund_context")
    if not isinstance(active_refund_context, dict):
        return state
    command = active_refund_context.get("confirmation_command")
    if not isinstance(command, str) or not command:
        return state
    return log_trace_step(
        state,
        message="Generated canonical refund confirmation command.",
        event_type="workflow.confirmation_command_generated",
        data={
            "kind": "refund_eligibility",
            "purchase_type": active_refund_context.get("purchase_type"),
            "purchase_id": active_refund_context.get("purchase_id"),
            "active_refund_stage": active_refund_context.get("stage"),
            "expected_command": command,
            "received_command": None,
            "matched_command": None,
        },
    )

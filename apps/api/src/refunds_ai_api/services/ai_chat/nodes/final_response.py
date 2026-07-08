"""Final-response graph node for AI chat."""

from __future__ import annotations

import json
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
from refunds_ai_api.services.ai_chat.model_context_projection import (
    ModelContextProjection,
    build_model_context_projection,
)
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.prompts import (
    SYSTEM_PROMPT,
    build_compact_model_context_message,
)
from refunds_ai_api.services.ai_chat.response_prompt_modules import (
    final_response_instructions_for_category,
)
from refunds_ai_api.services.ai_chat.responses import (
    ACCOUNT_DATA_REQUIRED_RESPONSE,
    CHAT_UNAVAILABLE_RESPONSE,
    sanitize_customer_response,
)
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.token_budget import (
    build_token_budget_breakdown,
    count_serialized,
    get_token_counter,
    log_token_budget_breakdown,
)
from refunds_ai_api.services.ai_chat.workflow import (
    build_refund_confirmation_command_offer,
    normalize_refund_confirmation_command,
)


def generate_final_response_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    if state.get("assistant_response"):
        return _return_deterministic_response(runtime, state)

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

    counter = get_token_counter(runtime.model)
    projection = build_model_context_projection(
        state=state,
        tool_results=tool_results,
        counter=counter,
    )
    response_instructions = final_response_instructions_for_category(
        projection.request_category
    )
    prompt_module_tokens = count_serialized(response_instructions, counter)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": state["message"]},
    ]
    compact_context_message = build_compact_model_context_message(
        state,
        tool_results=projection.projected_tool_results,
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
    if projection.projected_tool_results:
        projected_tool_result_label = (
            "Read-only account tool result: Projected for the current request. If "
            "deterministic response context sets primary_answer_source to "
            "active_result_set, do not broaden your answer beyond that scope: "
        )
        conversation_state = state.get("conversation_state")
        if not (
            isinstance(conversation_state, dict)
            and isinstance(conversation_state.get("active_result_set"), dict)
        ):
            projected_tool_result_label = "Read-only account tool result: "
        messages.append(
            {
                "role": "user",
                "content": projected_tool_result_label
                + f"{json.dumps(projection.projected_tool_results, default=str)}",
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
            "content": f"Response instructions: {response_instructions}",
        },
    )
    tools: list[dict[str, Any]] = []
    model_call_id = str(uuid4())
    model_started_at = datetime.now(UTC)
    model_started = perf_counter()
    state = log_trace_step(
        state,
        message="Sending final-response package to the model.",
        event_type="model.requested",
        data={
            "phase": "final_response",
            "model": runtime.model,
            "model_call_id": model_call_id,
            "started_at": model_started_at.isoformat(),
            "messages": messages,
            "tools": tools,
            "model_context": build_model_context_summary(
                state,
                tool_results=projection.projected_tool_results,
                page_reference=page_reference,
            ),
            "request_category": projection.request_category,
            "projection_reason": projection.projection_reason,
        },
    )

    try:
        turn = runtime.model_client.generate(messages=messages, tools=tools)
    except Exception as exc:
        token_budget = _log_model_token_budget(
            runtime,
            state,
            model_call_id=model_call_id,
            messages=messages,
            tools=tools,
            output_text=None,
            projection=projection,
            prompt_module_tokens=prompt_module_tokens,
        )
        model_completed_at = datetime.now(UTC)
        state = log_trace_step(
            state,
            message="Final model response request failed.",
            event_type="model.failure",
            level=logging.WARNING,
            data={
                "reason": exc.__class__.__name__,
                "detail": str(exc),
                "model": runtime.model,
                "model_call_id": model_call_id,
                "phase": "final_response",
                "status": "failed",
                "started_at": model_started_at.isoformat(),
                "completed_at": model_completed_at.isoformat(),
                "latency_ms": max(
                    0,
                    round((perf_counter() - model_started) * 1000),
                ),
                **_token_budget_lifecycle_fields(token_budget),
            },
        )
        return {
            **state,
            "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
            "error": "final_model_request_failed",
        }

    token_budget = _log_model_token_budget(
        runtime,
        state,
        model_call_id=model_call_id,
        messages=messages,
        tools=tools,
        output_text=turn.content,
        projection=projection,
        prompt_module_tokens=prompt_module_tokens,
    )
    model_completed_at = datetime.now(UTC)
    state = log_trace_step(
        state,
        message="Final-response model call completed.",
        event_type="model.completed",
        data={
            "model_call_id": model_call_id,
            "model": runtime.model,
            "phase": "final_response",
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
            "available_tools_count": 0,
            "tool_results_provided": len(tool_results),
            "conversation_state_summary": build_model_context_summary(
                state,
                tool_results=projection.projected_tool_results,
                page_reference=page_reference,
            ),
            "request_category": projection.request_category,
            "projection_reason": projection.projection_reason,
            **_token_budget_lifecycle_fields(token_budget),
        },
    )
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


def _return_deterministic_response(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    """Log token diagnostics for a backend-authored response that skips the model."""
    assistant_response = str(state.get("assistant_response") or "")
    counter = get_token_counter(str(state.get("model") or runtime.model))
    projection = build_model_context_projection(
        state=state,
        tool_results=state.get("tool_results", []),
        counter=counter,
    )
    output_tokens = count_serialized(assistant_response, counter)
    conversation_state_tokens = count_serialized(
        state.get("conversation_state", {}),
        counter,
    )
    return log_trace_step(
        state,
        message="Deterministic assistant response generated without a model call.",
        event_type="response.generated",
        data={
            "assistant_response": assistant_response,
            "response_source": "deterministic_backend",
            "request_category": projection.request_category,
            "projection_reason": projection.projection_reason,
            "raw_context_tokens": projection.raw_context_tokens,
            "projected_context_tokens": projection.projected_context_tokens,
            "token_savings_estimated": projection.token_savings_estimated,
            "prompt_module_tokens": 0,
            "tool_schema_tokens": 0,
            "tool_result_tokens": projection.projected_context_tokens,
            "conversation_state_tokens": conversation_state_tokens,
            "input_tokens_estimated": 0,
            "output_tokens_estimated": output_tokens,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "tokenizer": counter.name,
            "token_budget": {
                "tokenizer": counter.name,
                "input_tokens_estimated": 0,
                "output_tokens_estimated": output_tokens,
                "components": {
                    "deterministic_response": output_tokens,
                    "conversation_state": conversation_state_tokens,
                    "tool_results": projection.projected_context_tokens,
                },
            },
        },
    )


def _log_model_token_budget(
    runtime: Any,
    state: ChatGraphState,
    *,
    model_call_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    output_text: str | None,
    projection: ModelContextProjection | None = None,
    prompt_module_tokens: int | None = None,
) -> dict[str, Any]:
    page_context = state.get("page_context")
    page = (
        str(page_context.get("surface"))
        if isinstance(page_context, dict) and page_context.get("surface")
        else None
    )
    audit_session = state.get("audit_session")
    request_id = (
        str(getattr(audit_session, "id", model_call_id))
        if audit_session is not None
        else model_call_id
    )
    breakdown = build_token_budget_breakdown(
        model=runtime.model,
        messages=messages,
        tools=tools,
        current_user_message=state["message"],
        request_id=request_id,
        customer_id=state.get("customer_id"),
        page=page,
        output_text=output_text,
        counter=get_token_counter(runtime.model),
        diagnostics=(
            _projection_diagnostics(projection, prompt_module_tokens)
            if projection is not None
            else None
        ),
    )
    log_token_budget_breakdown(breakdown)
    return breakdown


def _token_budget_lifecycle_fields(breakdown: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_tokens_estimated": breakdown.get("input_tokens_total_estimated"),
        "output_tokens_estimated": breakdown.get("output_tokens_estimated"),
        "tokenizer": breakdown.get("tokenizer"),
        "raw_context_tokens": breakdown.get("raw_context_tokens"),
        "projected_context_tokens": breakdown.get("projected_context_tokens"),
        "token_savings_estimated": breakdown.get("token_savings_estimated"),
        "prompt_module_tokens": breakdown.get("prompt_module_tokens"),
        "tool_schema_tokens": breakdown.get("tool_schema_tokens"),
        "tool_result_tokens": breakdown.get("tool_result_tokens"),
        "conversation_state_tokens": breakdown.get("conversation_state_tokens"),
        "projection_reason": breakdown.get("projection_reason"),
        "request_category": breakdown.get("request_category"),
        "token_budget": breakdown,
    }


def _projection_diagnostics(
    projection: ModelContextProjection,
    prompt_module_tokens: int | None,
) -> dict[str, Any]:
    return {
        "raw_context_tokens": projection.raw_context_tokens,
        "projected_context_tokens": projection.projected_context_tokens,
        "token_savings_estimated": projection.token_savings_estimated,
        "prompt_module_tokens": prompt_module_tokens or 0,
        "projection_reason": projection.projection_reason,
        "request_category": projection.request_category,
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

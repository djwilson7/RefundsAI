"""Deterministic tool-call selection and trace logging."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_model_date_range_arguments
from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState, ModelToolCall
from refunds_ai_api.services.ai_chat.parsing import (
    parse_model_refund_eligibility_arguments,
    parse_model_refund_policy_arguments,
    parse_model_threshold_arguments,
)


def _prepare_deterministic_tool_execution(
    state: ChatGraphState,
    *,
    requested_call: ModelToolCall | None,
    target_tool_name: str,
    target_arguments: dict[str, Any],
    override_reason: str,
    same_tool_override_reason: str,
) -> tuple[ChatGraphState, str]:
    """Log deterministic tool routing and return the effective tool call id."""
    if requested_call is None:
        state = _log_forced_tool(
            state,
            target_tool_name,
            override_reason,
            target_arguments,
        )
        return state, _forced_tool_call_id(target_tool_name)

    model_arguments = _parse_model_arguments_for_tool(requested_call)
    if model_arguments is None:
        state = _log_invalid_arguments(state, requested_call)
        state = _log_forced_tool(
            state,
            target_tool_name,
            override_reason,
            target_arguments,
        )
        return state, _forced_tool_call_id(target_tool_name)

    if requested_call.name != target_tool_name:
        state = _log_workflow_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=override_reason,
            target_arguments=target_arguments,
        )
        state = _log_tool_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=override_reason,
            target_arguments=target_arguments,
        )
        return state, requested_call.id

    if model_arguments != target_arguments:
        state = _log_workflow_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=same_tool_override_reason,
            target_arguments=target_arguments,
            model_arguments=model_arguments,
        )
        state = _log_tool_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=same_tool_override_reason,
            target_arguments=target_arguments,
            model_arguments=model_arguments,
        )

    return _log_tool_executing(
        state,
        requested_call,
        target_tool_name,
        target_arguments,
    ), requested_call.id

def _complete_tool(
    state: ChatGraphState,
    *,
    tool_call_id: str,
    tool_name: str,
    result: dict[str, Any],
    message: str,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    tool_results = [
        {
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "result": result,
        }
    ]
    state = log_trace_step(
        state,
        message=message,
        event_type="tool_call.completed",
        data={
            "tool_name": tool_name,
            "result": result,
        },
    )
    state = log_trace_step(
        state,
        message="Deterministic workflow completed.",
        event_type="workflow.completed",
        data={
            "tool_name": tool_name,
            "result": result,
        },
    )
    return state, tool_results

def _log_forced_tool(
    state: ChatGraphState,
    tool_name: str,
    reason: str,
    target_arguments: dict[str, Any],
) -> ChatGraphState:
    labels = {
        "get_customer_purchase_history": (
            "No supported tool was requested for an account-domain message; "
            "forcing the read-only purchase-history tool."
        ),
        "get_purchase_count_by_amount_threshold": (
            "No supported tool was requested for a threshold purchase query; "
            "forcing the deterministic purchase-threshold count tool."
        ),
        "get_purchase_history_by_date_range": (
            "No supported tool was requested for a date-range purchase query; "
            "forcing the deterministic purchase-date-range tool."
        ),
        "get_refund_policy": (
            "No supported tool was requested for a refund-policy query; "
            "forcing the deterministic refund-policy tool."
        ),
        "get_refund_eligibility": (
            "No supported tool was requested for a refund-eligibility query; "
            "forcing the deterministic refund-eligibility tool."
        ),
        "validate_customer_account": (
            "No supported tool was requested for an account-validation query; "
            "forcing the read-only active-customer validation tool."
        ),
    }
    return log_trace_step(
        state,
        message=labels[tool_name],
        event_type="tool_call.forced",
        data={
            "tool_name": tool_name,
            "reason": reason,
            **_trace_arguments(target_arguments),
        },
    )

def _log_workflow_override(
    state: ChatGraphState,
    *,
    requested_tool_name: str,
    target_tool_name: str,
    reason: str,
    target_arguments: dict[str, Any],
    model_arguments: dict[str, Any] | None = None,
) -> ChatGraphState:
    data = {
        "requested_tool_name": requested_tool_name,
        "tool_name": target_tool_name,
        "reason": reason,
        **_trace_arguments(target_arguments),
    }
    if model_arguments is not None:
        data["model_arguments"] = model_arguments
    return log_trace_step(
        state,
        message="Deterministic workflow overrode a conflicting model tool call.",
        event_type="workflow.tool_overridden",
        data=data,
    )

def _log_tool_override(
    state: ChatGraphState,
    *,
    requested_tool_name: str,
    target_tool_name: str,
    reason: str,
    target_arguments: dict[str, Any],
    model_arguments: dict[str, Any] | None = None,
) -> ChatGraphState:
    data = {
        "requested_tool_name": requested_tool_name,
        "tool_name": target_tool_name,
        "reason": reason,
        **_trace_arguments(target_arguments),
    }
    if model_arguments is not None:
        data["model_arguments"] = model_arguments
    return log_trace_step(
        state,
        message="Overriding model tool selection with deterministic workflow routing.",
        event_type="tool_call.overridden",
        data=data,
    )

def _log_tool_executing(
    state: ChatGraphState,
    requested_call: ModelToolCall,
    target_tool_name: str,
    target_arguments: dict[str, Any],
) -> ChatGraphState:
    return log_trace_step(
        state,
        message=f"Executing backend {target_tool_name} tool.",
        event_type="tool_call.executing",
        data={
            "tool_call_id": requested_call.id,
            "tool_name": target_tool_name,
            "model_arguments": requested_call.arguments,
            **_trace_arguments(target_arguments),
        },
    )

def _log_invalid_arguments(
    state: ChatGraphState,
    tool_call: ModelToolCall,
) -> ChatGraphState:
    return log_trace_step(
        state,
        message=f"Ignoring invalid {tool_call.name} tool arguments.",
        event_type="tool_call.ignored",
        data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
    )

def _parse_model_arguments_for_tool(
    tool_call: ModelToolCall,
) -> dict[str, Any] | None:
    if tool_call.name == "get_purchase_count_by_amount_threshold":
        return parse_model_threshold_arguments(tool_call.arguments)
    if tool_call.name == "get_purchase_history_by_date_range":
        return parse_model_date_range_arguments(tool_call.arguments)
    if tool_call.name == "get_refund_policy":
        return parse_model_refund_policy_arguments(tool_call.arguments)
    if tool_call.name == "get_refund_eligibility":
        return parse_model_refund_eligibility_arguments(tool_call.arguments)
    if tool_call.name == "get_customer_purchase_history":
        return {} if not tool_call.arguments else tool_call.arguments
    if tool_call.name == "validate_customer_account":
        return {} if not tool_call.arguments else tool_call.arguments
    return None

def _first_supported_tool_call(state: ChatGraphState) -> ModelToolCall | None:
    for tool_call in state.get("tool_calls", []):
        if tool_call.name in {
            "get_customer_purchase_history",
            "get_purchase_count_by_amount_threshold",
            "get_purchase_history_by_date_range",
            "get_refund_policy",
            "get_refund_eligibility",
            "validate_customer_account",
        }:
            return tool_call
    return None

def _first_tool_call(
    state: ChatGraphState,
    tool_name: str,
) -> ModelToolCall | None:
    for tool_call in state.get("tool_calls", []):
        if tool_call.name == tool_name:
            return tool_call
    return None

def _forced_tool_call_id(tool_name: str) -> str:
    return f"forced-{tool_name.replace('_', '-')}"

def _trace_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return legacy-compatible tool trace arguments."""
    return {key: value for key, value in arguments.items() if key != "label"}

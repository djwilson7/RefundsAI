"""Deterministic tool-call selection and trace logging."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

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
    source = "model_requested"
    if requested_call is None:
        state = _log_forced_tool(
            state,
            target_tool_name,
            override_reason,
            target_arguments,
        )
        source = "deterministic_forced"
    else:
        model_arguments = _parse_model_arguments_for_tool(requested_call)
        if model_arguments is None:
            state = _log_invalid_arguments(state, requested_call)
            state = _log_forced_tool(
                state,
                target_tool_name,
                override_reason,
                target_arguments,
            )
            source = "deterministic_forced"
        elif requested_call.name != target_tool_name:
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
            source = "deterministic_override"
        elif model_arguments != target_arguments:
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
            source = "deterministic_override"

    return _start_tool_lifecycle(
        state,
        target_tool_name,
        target_arguments,
        source=source,
    )

def _complete_tool(
    state: ChatGraphState,
    *,
    tool_call_id: str,
    tool_name: str,
    result: dict[str, Any],
    message: str,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    lifecycle = dict(state.get("_tool_lifecycles", {})).get(tool_call_id, {})
    completed_at = datetime.now(UTC)
    started_at = lifecycle.get("started_at")
    started_counter = lifecycle.get("started_counter")
    latency_ms = (
        max(0, round((perf_counter() - started_counter) * 1000))
        if isinstance(started_counter, float)
        else None
    )
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
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "status": "completed",
            "source": lifecycle.get("source"),
            "workflow": lifecycle.get("workflow"),
            "operation": lifecycle.get("operation"),
            "started_at": started_at,
            "completed_at": completed_at.isoformat(),
            "latency_ms": latency_ms,
            "input_summary": lifecycle.get("input_summary"),
            "output_summary": _tool_output_summary(tool_name, result),
            "backend_category": _tool_backend_category(tool_name),
            "customer_id": lifecycle.get("customer_id"),
            "purchase_id": lifecycle.get("purchase_id"),
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


def _start_tool_lifecycle(
    state: ChatGraphState,
    tool_name: str,
    target_arguments: dict[str, Any],
    *,
    source: str,
) -> tuple[ChatGraphState, str]:
    """Emit a tool start event and retain timing until completion."""
    tool_call_id = str(uuid4())
    started_at = datetime.now(UTC)
    lifecycle = {
        "source": source,
        "workflow": state.get("workflow_kind"),
        "operation": _tool_operation(tool_name),
        "started_at": started_at.isoformat(),
        "started_counter": perf_counter(),
        "input_summary": _tool_input_summary(tool_name),
        "customer_id": state.get("customer_id"),
        "purchase_id": _purchase_id_from_arguments(target_arguments),
    }
    lifecycles = {**state.get("_tool_lifecycles", {}), tool_call_id: lifecycle}
    state = log_trace_step(
        {**state, "_tool_lifecycles": lifecycles},
        message=f"Backend {tool_name} tool started.",
        event_type="tool_call.executing",
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "status": "started",
            "source": source,
            "workflow": lifecycle["workflow"],
            "operation": lifecycle["operation"],
            "started_at": lifecycle["started_at"],
            "input_summary": lifecycle["input_summary"],
            "backend_category": _tool_backend_category(tool_name),
            "customer_id": lifecycle["customer_id"],
            "purchase_id": lifecycle["purchase_id"],
            **_trace_arguments(target_arguments),
        },
    )
    return state, tool_call_id

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
    started_at = datetime.now(UTC)
    lifecycle = {
        "source": "model_requested",
        "workflow": state.get("workflow_kind"),
        "operation": _tool_operation(target_tool_name),
        "started_at": started_at.isoformat(),
        "started_counter": perf_counter(),
        "input_summary": _tool_input_summary(target_tool_name),
        "customer_id": state.get("customer_id"),
        "purchase_id": _purchase_id_from_arguments(target_arguments),
    }
    lifecycles = {
        **state.get("_tool_lifecycles", {}),
        requested_call.id: lifecycle,
    }
    return log_trace_step(
        {**state, "_tool_lifecycles": lifecycles},
        message=f"Executing backend {target_tool_name} tool.",
        event_type="tool_call.executing",
        data={
            "tool_call_id": requested_call.id,
            "tool_name": target_tool_name,
            "status": "started",
            "source": lifecycle["source"],
            "workflow": lifecycle["workflow"],
            "operation": lifecycle["operation"],
            "started_at": lifecycle["started_at"],
            "input_summary": lifecycle["input_summary"],
            "backend_category": _tool_backend_category(target_tool_name),
            "customer_id": lifecycle["customer_id"],
            "purchase_id": lifecycle["purchase_id"],
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

def _trace_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return legacy-compatible tool trace arguments."""
    return {key: value for key, value in arguments.items() if key != "label"}


def _forced_tool_call_id(tool_name: str) -> str:
    """Return the legacy deterministic id used by refund mutation orchestration."""
    return f"forced-{tool_name.replace('_', '-')}"


def _tool_operation(tool_name: str) -> str:
    return {
        "get_customer_purchase_history": "list",
        "get_purchase_count_by_amount_threshold": "count",
        "get_purchase_history_by_date_range": "list",
        "get_refund_policy": "policy_lookup",
        "get_refund_eligibility": "eligibility",
        "validate_customer_account": "validation",
    }.get(tool_name, tool_name)


def _tool_input_summary(tool_name: str) -> str:
    return {
        "get_customer_purchase_history": "customer purchase history",
        "get_purchase_count_by_amount_threshold": "purchase amount threshold",
        "get_purchase_history_by_date_range": "purchase date range",
        "get_refund_policy": "refund policy lookup",
        "get_refund_eligibility": "refund eligibility evaluation",
        "validate_customer_account": "customer account validation",
    }.get(tool_name, tool_name)


def _tool_output_summary(tool_name: str, result: dict[str, Any]) -> str:
    if tool_name == "get_customer_purchase_history":
        aggregates = result.get("aggregates")
        if isinstance(aggregates, dict):
            count = aggregates.get("total_purchase_count", 0)
            total = aggregates.get("total_amount_dollars", "0.00")
            return f"{count} purchases, ${total}"
    summary = result.get("summary")
    if isinstance(summary, str):
        return summary
    count = result.get("purchase_count", result.get("count"))
    return f"{count} results" if isinstance(count, int) else "completed"


def _tool_backend_category(tool_name: str) -> str:
    if tool_name in {"get_refund_eligibility", "validate_customer_account"}:
        return "backend_validation"
    return "backend_read"


def _purchase_id_from_arguments(arguments: dict[str, Any]) -> str | None:
    purchase_id = arguments.get("purchase_id")
    if isinstance(purchase_id, str):
        return purchase_id
    purchase_ids = arguments.get("purchase_ids")
    if isinstance(purchase_ids, list) and len(purchase_ids) == 1:
        return str(purchase_ids[0])
    return None

"""Structured trace logging and compact trace summaries for AI chat."""

from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path
from typing import Any

from .models import ChatGraphState

logger = logging.getLogger("refunds_ai_api.chat")
console_logger = logging.getLogger("uvicorn.error")

def log_trace_step(
    state: ChatGraphState,
    *,
    message: str,
    event_type: str,
    data: dict[str, Any] | None = None,
    level: int = logging.INFO,
) -> ChatGraphState:
    """Emit one console-visible sequential trace event for chat orchestration."""
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame is not None else None
    file_path = (
        str(Path(caller_frame.f_code.co_filename).resolve())
        if caller_frame is not None
        else str(Path(__file__).resolve())
    )
    resolved_file = Path(file_path)
    if resolved_file.parent.name == "ai_chat":
        file_path = str(resolved_file.parent.parent / "ai_chat.py")
    elif (
        resolved_file.parent.name == "nodes"
        and resolved_file.parent.parent.name == "ai_chat"
    ):
        file_path = str(resolved_file.parent.parent.parent / "ai_chat.py")
    line_number = caller_frame.f_lineno if caller_frame is not None else 0
    step = int(state.get("trace_step", 1))
    event = {
        "type": event_type,
        "step": step,
        "file": file_path,
        "line": line_number,
        "message": message,
        "data": data or {},
    }
    logger.log(
        level,
        "ai.chat.trace %s",
        json.dumps(event, default=str, sort_keys=True),
        extra={"event": event},
    )
    console_logger.log(
        level,
        "%s",
        format_trace_console_message(event),
    )
    return {**state, "trace_step": step + 1}


def format_trace_console_message(event: dict[str, Any]) -> str:
    """Return a compact, human-readable console summary for one trace event."""
    event_type = str(event.get("type", "unknown"))
    step = event.get("step", "?")
    message = str(event.get("message", "")).strip()
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    details = trace_console_details(event_type, data)
    summary = f"AI graph step {step}: {humanize_event_type(event_type)}"
    if message:
        summary = f"{summary} - {message}"
    if details:
        summary = f"{summary} ({details})"
    return summary


def build_model_context_summary(
    state: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    page_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return compact context describing what the model can use."""
    effective_tool_results = tool_results
    if effective_tool_results is None:
        maybe_tool_results = state.get("tool_results")
        effective_tool_results = maybe_tool_results if isinstance(maybe_tool_results, list) else []

    return {
        "conversation_state": summarize_conversation_state(
            state.get("conversation_state")
        ),
        "page_context": page_context_label(state.get("page_context")),
        "page_reference": page_reference_label(page_reference or state.get("page_reference")),
        "tool_results": summarize_tool_results_for_context(effective_tool_results),
        "intents": summarize_intents(state),
        "blocked_intent": state.get("blocked_intent"),
    }


def humanize_event_type(event_type: str) -> str:
    """Convert a dotted trace event type into readable console text."""
    labels = {
        "graph.started": "Graph started",
        "graph.stopped": "Graph stopped",
        "message.received": "Message received",
        "model.failure": "Model unavailable",
        "model.invalid_tool_output": "Invalid model tool output",
        "model.requested": "Model requested",
        "response.blocked": "Response blocked",
        "response.generated": "Response generated",
        "route.response_returned": "Route response returned",
        "tool_call.completed": "Tool completed",
        "tool_call.executing": "Tool executing",
        "tool_call.forced": "Tool forced",
        "tool_call.ignored": "Tool ignored",
        "tool_call.overridden": "Tool overridden",
        "tool_call.requested": "Tool requested",
        "tool_call.skipped": "Tool skipped",
    }
    return labels.get(event_type, event_type.replace("_", " ").replace(".", " ").title())


def trace_console_details(event_type: str, data: dict[str, Any]) -> str:
    """Return event-specific details without dumping nested payloads."""
    if event_type == "message.received":
        return join_trace_fields(
            message=shorten_text(data.get("message")),
            customer=short_id(data.get("customer_id")),
            purchase=short_id(data.get("purchase_id")),
            page=page_context_label(data.get("page_context")),
            state=summarize_conversation_state(data.get("conversation_state")),
        )

    if event_type == "graph.started":
        return join_trace_fields(
            customer=short_id(data.get("customer_id")),
            purchase=short_id(data.get("purchase_id")),
            page=page_context_label(data.get("page_context")),
            model=data.get("model"),
        )

    if event_type == "model.requested":
        return join_trace_fields(
            phase=data.get("phase"),
            model=data.get("model"),
            messages=count_items(data.get("messages")),
            tools=tool_names(data.get("tools")),
            context=summarize_model_context(data.get("model_context")),
        )

    if event_type == "tool_call.requested":
        return join_trace_fields(
            tools=tool_call_names(data.get("tool_calls")),
            content=shorten_text(data.get("model_content")),
        )

    if event_type in {
        "tool_call.executing",
        "tool_call.completed",
        "tool_call.forced",
        "tool_call.overridden",
        "tool_call.ignored",
    }:
        return tool_trace_details(event_type, data)

    if event_type == "tool_call.skipped":
        return join_trace_fields(reason=data.get("reason"))

    if event_type == "response.blocked":
        return join_trace_fields(
            reason=data.get("reason"),
            product=data.get("product_reference"),
            context=summarize_model_context(data.get("model_context")),
        )

    if event_type == "response.generated":
        return join_trace_fields(
            model=data.get("model"),
            tools=data.get("tool_result_count"),
            response=shorten_text(data.get("assistant_response")),
        )

    if event_type == "route.response_returned":
        response = data.get("response") if isinstance(data.get("response"), dict) else {}
        message = response.get("message") if isinstance(response.get("message"), dict) else {}
        return join_trace_fields(
            model=data.get("model"),
            graph_ready=data.get("graph_ready"),
            response=shorten_text(message.get("content")),
            state=summarize_conversation_state(response.get("conversation_state")),
        )

    if event_type in {"graph.stopped", "model.failure", "model.invalid_tool_output"}:
        return join_trace_fields(
            reason=data.get("reason"),
            model=data.get("model"),
            detail=shorten_text(data.get("detail")),
        )

    return summarize_flat_trace_data(data)


def tool_trace_details(event_type: str, data: dict[str, Any]) -> str:
    """Return concise details for one tool-related trace event."""
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    return join_trace_fields(
        tool=data.get("tool_name"),
        requested=data.get("requested_tool_name"),
        reason=data.get("reason"),
        customer=short_id(data.get("customer_id") or data.get("effective_customer_id")),
        purchase_ids=summarize_ids(data.get("purchase_ids") or data.get("effective_purchase_ids")),
        context=data.get("context"),
        result=summarize_tool_result(result) if result else None,
        arguments="invalid" if event_type == "tool_call.ignored" else None,
    )


def summarize_tool_result(result: dict[str, Any]) -> str:
    """Return a compact description of model-facing tool output."""
    if "aggregates" in result and isinstance(result["aggregates"], dict):
        aggregates = result["aggregates"]
        return (
            f"{aggregates.get('total_purchase_count', 0)} purchases, "
            f"${aggregates.get('total_amount_dollars', '0.00')}"
        )
    if "purchase_count" in result:
        return (
            f"{result.get('purchase_count', 0)} purchases, "
            f"{result.get('eligible_count', 0)} eligible, "
            f"{result.get('blocked_count', 0)} blocked"
        )
    if "count" in result:
        return f"{result.get('count', 0)} matches"
    if "sections" in result:
        sections = result.get("sections")
        return f"{count_items(sections)} policy sections"
    return summarize_flat_trace_data(result)


def summarize_model_context(value: Any) -> str | None:
    """Return compact context the model had available for an event."""
    if not isinstance(value, dict):
        return None
    return join_trace_fields(
        state=value.get("conversation_state"),
        page=value.get("page_context"),
        page_ref=value.get("page_reference"),
        provided=value.get("tool_results"),
        intents=value.get("intents"),
        blocked=value.get("blocked_intent"),
    )


def summarize_conversation_state(value: Any) -> str | None:
    """Return compact selected conversation state without full payloads."""
    if not isinstance(value, dict):
        return None

    selected_ids = value.get("selected_purchase_ids")
    refund_ids = value.get("selected_refund_purchase_ids")
    date_range = value.get("selected_date_range")
    current_page = value.get("current_page")
    active_refund_context = value.get("active_refund_context")
    return join_trace_fields(
        type=value.get("selected_purchase_type"),
        product=value.get("selected_product"),
        purchase=short_id(value.get("selected_purchase_id")),
        selected=count_items(selected_ids),
        scope=value.get("selected_scope_label"),
        policy=value.get("selected_policy_scope"),
        date=date_range.get("label") if isinstance(date_range, dict) else None,
        refund_selected=count_items(refund_ids),
        refund_context=value.get("selected_refund_context"),
        active_refund=active_refund_context_label(active_refund_context),
        page=page_reference_label(current_page),
    )


def summarize_tool_results_for_context(tool_results: list[dict[str, Any]]) -> str | None:
    """Return compact summary of tool data made available to the model."""
    if not tool_results:
        return None

    summaries = []
    for tool_result in tool_results[:3]:
        if not isinstance(tool_result, dict):
            continue
        name = tool_result.get("name")
        result = tool_result.get("result")
        if isinstance(name, str) and isinstance(result, dict):
            summaries.append(f"{name}:{summarize_tool_result(result)}")

    if not summaries:
        return None
    suffix = f"; +{len(tool_results) - 3}" if len(tool_results) > 3 else ""
    return "; ".join(summaries) + suffix


def summarize_intents(state: dict[str, Any]) -> str | None:
    """Return compact graph intent flags that affect model/tool routing."""
    labels = []
    intent_fields = (
        ("account", "account_fact_intent"),
        ("policy", "policy_lookup_intent"),
        ("eligibility", "eligibility_lookup_intent"),
    )
    for label, intent_field in intent_fields:
        if state.get(intent_field) is True:
            labels.append(label)
    return ",".join(labels) if labels else None


def active_refund_context_label(value: Any) -> str | None:
    """Return a compact label for active refund workflow state."""
    if not isinstance(value, dict):
        return None
    return join_trace_fields(
        product=value.get("product_name"),
        purchase=short_id(value.get("purchase_id")),
        stage=value.get("stage"),
        next=value.get("next_action"),
    )


def summarize_flat_trace_data(data: dict[str, Any]) -> str:
    """Summarize shallow scalar data while ignoring nested payloads."""
    fields: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str | int | float | bool) or value is None:
            fields[key] = shorten_text(value)
    return join_trace_fields(**fields)


def join_trace_fields(**fields: Any) -> str:
    """Join non-empty trace fields into a stable compact string."""
    parts = []
    for key, value in fields.items():
        if value is None or value == "" or value == []:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def count_items(value: Any) -> int | None:
    """Return item count for list-like trace fields."""
    return len(value) if isinstance(value, list) else None


def tool_names(tools: Any) -> str | None:
    """Return compact model tool names from OpenAI tool schemas."""
    if not isinstance(tools, list):
        return None
    names = [str(tool.get("name")) for tool in tools if isinstance(tool, dict) and tool.get("name")]
    if not names:
        return "none"
    return ", ".join(names)


def tool_call_names(tool_calls: Any) -> str | None:
    """Return compact model-requested tool names."""
    if not isinstance(tool_calls, list):
        return None
    names = [
        str(call.get("name"))
        for call in tool_calls
        if isinstance(call, dict) and call.get("name")
    ]
    return ", ".join(names) if names else "none"


def page_context_label(page_context: Any) -> str | None:
    """Return a compact page context label."""
    if not isinstance(page_context, dict):
        return None
    surface = page_context.get("surface")
    purchase_id = page_context.get("purchase_id")
    if purchase_id:
        return f"{surface}:{short_id(purchase_id)}"
    return str(surface) if surface else None


def page_reference_label(page_reference: Any) -> str | None:
    """Return a compact resolved page reference label."""
    if not isinstance(page_reference, dict):
        return None

    surface = page_reference.get("surface")
    purchase = page_reference.get("purchase")
    if isinstance(purchase, dict):
        product = purchase.get("product_name")
        purchase_type = purchase.get("purchase_type")
        purchase_id = short_id(purchase.get("id"))
        return join_trace_fields(
            surface=surface,
            product=product,
            type=purchase_type,
            id=purchase_id,
        )
    return str(surface) if surface else None


def summarize_ids(value: Any) -> str | None:
    """Return compact id list summary."""
    if not isinstance(value, list):
        return None
    if not value:
        return "none"
    visible = [short_id(item) for item in value[:3]]
    suffix = f"+{len(value) - 3}" if len(value) > 3 else ""
    return ",".join(item for item in visible if item) + suffix


def short_id(value: Any) -> str | None:
    """Return a short readable identifier for UUID-like values."""
    if not isinstance(value, str) or not value:
        return None
    if len(value) >= 8 and "-" in value:
        return value[:8]
    return value


def shorten_text(value: Any, *, limit: int = 96) -> str | None:
    """Return compact single-line text for console logs."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."

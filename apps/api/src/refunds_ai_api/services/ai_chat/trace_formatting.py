"""Readable structured console formatting for AI chat trace events."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

MAX_TRACE_ITEMS = 10
MAX_ACTIVE_RESULT_SET_PREVIEW_ITEMS = 5
MAX_RESPONSE_PREVIEW_CHARS = 160
MAX_MESSAGE_PREVIEW_CHARS = 240


def format_debug_block(title: str, data: Mapping[str, Any]) -> str:
    """Format one stable YAML-like debug block."""
    lines = [f"--- {title} ---"]
    lines.extend(_format_mapping(data, indent=0))
    lines.append(f"--- end {title} ---")
    return "\n".join(lines)


def format_sequence_block(title: str, items: Sequence[Any]) -> str:
    """Format one bounded list block."""
    return format_debug_block(title, {"items": list(items)})


def format_trace_detail_block(event_type: str, data: Mapping[str, Any]) -> str | None:
    """Return the structured console detail block for a trace event."""
    if event_type == "message.received":
        return format_debug_block("Incoming Message", summarize_incoming_message(data))
    if event_type == "model.requested":
        return format_debug_block("Model Request", summarize_model_request(data))
    if event_type == "tool_call.requested":
        return format_debug_block("Model Tool Selection", summarize_tool_selection(data))
    if event_type == "workflow.classified":
        return format_debug_block(
            "Workflow Classification",
            summarize_workflow_classification(data),
        )
    if event_type == "workflow.context_resolved":
        return format_debug_block("Workflow Context", summarize_workflow_context(data))
    if event_type == "workflow.executing":
        return format_debug_block("Workflow Execution", summarize_workflow_execution(data))
    if event_type == "tool_call.executing":
        return format_debug_block("Tool Execution", summarize_tool_execution(data))
    if event_type == "tool_call.completed":
        return format_debug_block("Tool Result", summarize_tool_result_event(data))
    if event_type == "workflow.state_updated":
        return format_debug_block("Workflow State Update", summarize_state_update(data))
    if event_type == "response.generated":
        return format_debug_block("Assistant Response", summarize_assistant_response(data))
    if event_type == "route.response_returned":
        return format_debug_block("API Response", summarize_api_response(data))
    if event_type in {"response.blocked", "workflow.blocked"}:
        return format_debug_block("Workflow Blocked", summarize_blocked_workflow(data))
    return None


def summarize_incoming_message(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe incoming-message trace fields."""
    return {
        "customer_id": data.get("customer_id"),
        "page": _page_label(data.get("page_context")),
        "message": preview_text(
            data.get("message"),
            max_chars=MAX_MESSAGE_PREVIEW_CHARS,
        ),
        "conversation_state": summarize_conversation_state(
            _mapping_or_none(data.get("conversation_state"))
        ),
    }


def summarize_model_request(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe model-request trace fields without raw prompts."""
    messages = data.get("messages")
    tools = data.get("tools")
    model_context = _mapping_or_none(data.get("model_context")) or {}
    response_context = _extract_response_context(messages)
    summary: dict[str, Any] = {
        "phase": data.get("phase"),
        "model": data.get("model"),
        "message_count": len(messages) if isinstance(messages, list) else 0,
        "available_tools": _tool_names(tools),
    }
    if response_context:
        summary["primary_answer_source"] = response_context.get("primary_answer_source")
        active_result_set = _mapping_or_none(response_context.get("active_result_set"))
        if active_result_set is not None:
            active_result_set_summary: dict[str, Any] = {
                "label": active_result_set.get("label"),
                "count": active_result_set.get("count"),
            }
            if response_context.get("primary_answer_source") == "active_result_set":
                items_preview = _active_result_set_items_preview(
                    active_result_set.get("items")
                )
                if items_preview:
                    active_result_set_summary["items_preview"] = items_preview
            summary["provided"] = {
                "active_result_set": active_result_set_summary,
                "raw_tool_result": model_context.get("tool_results"),
            }
    summary["context"] = {
        "page": model_context.get("page_context"),
        "page_reference": model_context.get("page_reference"),
        "active_scope": _active_scope(model_context),
        "provided": model_context.get("tool_results"),
        "intents": _split_csv(model_context.get("intents")),
        "blocked_intent": model_context.get("blocked_intent"),
    }
    return summary


def summarize_tool_selection(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return model tool-selection summary."""
    tool_calls = data.get("tool_calls")
    return {
        "requested_tools": _tool_call_names(tool_calls),
        "assistant_content_preview": preview_text(data.get("model_content")),
        "conflict_with_deterministic_route": False,
    }


def summarize_workflow_classification(value: Any) -> dict[str, Any]:
    """Return object-operation workflow classification fields."""
    data = _object_to_mapping(value)
    workflow_kind = _get_attr_or_key(data, "kind")
    object_kind = _get_attr_or_key(data, "object") or _nested_attr(
        data,
        "conversation_object",
        "kind",
    )
    operation_kind = _nested_attr(data, "operation", "operation") or _get_attr_or_key(
        data,
        "operation",
    )
    return {
        "workflow": {
            "kind": _enum_value(workflow_kind),
            "reason": _get_attr_or_key(data, "reason"),
            "confidence": _get_attr_or_key(data, "confidence"),
        },
        "conversation_object": {
            "kind": _enum_value(object_kind),
            "label": _get_attr_or_key(data, "object_label")
            or _nested_attr(data, "conversation_object", "label"),
            "source": _nested_attr(data, "conversation_object", "source"),
        },
        "operation": {
            "kind": _enum_value(operation_kind),
            "reason": _get_attr_or_key(data, "operation_reason")
            or _nested_attr(data, "operation", "reason"),
            "confidence": _nested_attr(data, "operation", "confidence"),
        },
        "lookup": {
            "key": _lookup_key(_enum_value(object_kind), _enum_value(operation_kind)),
            "result": _enum_value(workflow_kind),
        },
    }


def summarize_workflow_context(value: Any) -> dict[str, Any]:
    """Return workflow context fields that matter for routing."""
    data = _object_to_mapping(value)
    eligibility = _get_attr_or_key(data, "eligibility_resolution")
    return {
        "customer_id": _get_attr_or_key(data, "customer_id"),
        "page_reference": _page_reference_label(_get_attr_or_key(data, "page_reference")),
        "policy_lookup_query": _get_attr_or_key(data, "policy_lookup_query"),
        "eligibility_resolution": _summarize_eligibility_resolution(eligibility),
        "resolved_purchase": _purchase_label(_get_attr_or_key(data, "resolved_purchase")),
        "unresolved_product_reference": _get_attr_or_key(
            data,
            "unresolved_product_reference",
        ),
        "threshold_query": _get_attr_or_key(data, "threshold_query"),
        "date_range_query": _get_attr_or_key(data, "date_range_query"),
    }


def summarize_workflow_execution(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic workflow execution route summary."""
    workflow = data.get("kind")
    return {
        "workflow": workflow,
        "reason": data.get("reason"),
        "selected_route": {
            "tool": _tool_for_workflow(workflow),
            "source": "deterministic_lookup",
        },
        "model_requested_tool": data.get("requested_tool_name"),
        "override_required": bool(data.get("requested_tool_name"))
        and data.get("requested_tool_name") != _tool_for_workflow(workflow),
    }


def summarize_tool_execution(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe tool execution arguments."""
    return {
        "tool": data.get("tool_name"),
        "arguments": _tool_arguments(data),
    }


def summarize_tool_result_event(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe tool result summary for a completed tool event."""
    tool_name = data.get("tool_name")
    result = _mapping_or_none(data.get("result")) or {}
    summary = summarize_tool_result(str(tool_name), result)
    return {
        "tool": tool_name,
        **summary,
    }


def summarize_tool_result(tool_name: str, result: Mapping[str, Any]) -> dict[str, Any]:
    """Return bounded safe fields for a tool result."""
    if "aggregates" in result and isinstance(result["aggregates"], Mapping):
        aggregates = result["aggregates"]
        purchases = result.get("purchases")
        return {
            "summary": (
                f"{aggregates.get('total_purchase_count', 0)} purchases, "
                f"${aggregates.get('total_amount_dollars', '0.00')}"
            ),
            "aggregates": {
                "total_purchase_count": aggregates.get("total_purchase_count"),
                "total_spend": f"${aggregates.get('total_amount_dollars', '0.00')}",
            },
            "items_preview": _purchase_items_preview(purchases),
        }
    if "purchase_count" in result:
        purchases = result.get("purchases")
        return {
            "summary": (
                f"{result.get('purchase_count', 0)} purchases, "
                f"{result.get('eligible_count', 0)} eligible, "
                f"{result.get('blocked_count', 0)} blocked"
            ),
            "result": {
                "purchase_count": result.get("purchase_count"),
                "eligible_count": result.get("eligible_count"),
                "blocked_count": result.get("blocked_count"),
                "items": _eligibility_items_preview(purchases),
            },
        }
    if "count" in result:
        return {
            "summary": f"{result.get('count', 0)} matches",
            "result": {
                "count": result.get("count"),
                "matching_purchase_count": len(result.get("matching_purchase_ids", []))
                if isinstance(result.get("matching_purchase_ids"), list)
                else 0,
            },
        }
    if "sections" in result:
        sections = result.get("sections")
        return {
            "summary": f"{len(sections) if isinstance(sections, list) else 0} policy sections",
            "result": {
                "scope": result.get("scope"),
                "purchase_type": result.get("purchase_type"),
                "section_count": len(sections) if isinstance(sections, list) else 0,
            },
        }
    return {"summary": tool_name, "result": dict(result)}


def summarize_state_update(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return workflow state after deterministic updates."""
    active_result_set = _mapping_or_none(data.get("active_result_set"))
    return {
        "active_workflow": summarize_active_workflow(data.get("active_workflow")),
        "active_result_set": summarize_active_result_set(active_result_set),
        "active_purchase": summarize_active_purchase(data.get("active_purchase")),
        "refund_context": _refund_context_from_state(data),
    }


def summarize_assistant_response(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return final assistant response metadata."""
    response = str(data.get("assistant_response") or "")
    return {
        "model": data.get("model"),
        "tool_results_used": data.get("tool_result_count"),
        "response_preview": preview_text(
            response,
            max_chars=MAX_RESPONSE_PREVIEW_CHARS,
        ),
        "response_length_chars": len(response),
    }


def summarize_api_response(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return route response metadata."""
    response = _mapping_or_none(data.get("response")) or {}
    message = _mapping_or_none(response.get("message")) or {}
    state = _mapping_or_none(response.get("conversation_state")) or {}
    return {
        "graph_ready": data.get("graph_ready"),
        "model": data.get("model"),
        "response_preview": preview_text(
            message.get("content"),
            max_chars=MAX_RESPONSE_PREVIEW_CHARS,
        ),
        "state": {
            "active_workflow": _active_workflow_kind(state),
            "active_scope": state.get("selected_scope_label"),
            "selected_count": _count(state.get("selected_purchase_ids")),
            "refund_selected": _count(state.get("selected_refund_purchase_ids")),
        },
    }


def summarize_blocked_workflow(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return blocked workflow details with readable fallback reason."""
    model_context = _mapping_or_none(data.get("model_context")) or {}
    reason = data.get("reason") or "refund_mutation_not_ready"
    return {
        "workflow": data.get("kind"),
        "reason": reason,
        "object": {
            "kind": data.get("object"),
            "label": data.get("object_label"),
        },
        "operation": data.get("operation"),
        "active_refund_context": model_context.get("conversation_state"),
        "user_response": preview_text(
            data.get("assistant_response") or data.get("response"),
            max_chars=MAX_RESPONSE_PREVIEW_CHARS,
        ),
        "product_reference": data.get("product_reference"),
    }


def summarize_conversation_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return compact conversation state for structured logs."""
    if not isinstance(state, Mapping):
        return {}
    active_result_set = _mapping_or_none(state.get("active_result_set"))
    active_purchase = _mapping_or_none(state.get("active_purchase"))
    active_workflow = _mapping_or_none(state.get("active_workflow"))
    return {
        "selected_type": state.get("selected_purchase_type"),
        "selected_count": _count(state.get("selected_purchase_ids")),
        "scope": state.get("selected_scope_label"),
        "active_workflow": active_workflow.get("kind") if active_workflow else None,
        "active_result_set": summarize_active_result_set(active_result_set),
        "active_purchase": summarize_active_purchase(active_purchase),
    }


def summarize_active_workflow(value: Any) -> dict[str, Any] | None:
    """Return active workflow summary."""
    active_workflow = _mapping_or_none(value)
    if active_workflow is None:
        return None
    return {
        "kind": active_workflow.get("kind"),
        "tool": active_workflow.get("last_tool_name"),
        "operation": active_workflow.get("operation"),
    }


def summarize_active_result_set(value: Any) -> dict[str, Any] | None:
    """Return active result-set summary."""
    active_result_set = _mapping_or_none(value)
    if active_result_set is None:
        return None
    purchase_ids = active_result_set.get("purchase_ids")
    return {
        "type": active_result_set.get("type"),
        "label": active_result_set.get("label"),
        "count": _count(purchase_ids),
        "items": _id_items_preview(purchase_ids),
    }


def summarize_active_purchase(value: Any) -> dict[str, Any] | None:
    """Return active purchase summary."""
    active_purchase = _mapping_or_none(value)
    if active_purchase is None:
        return None
    return {
        "purchase_id": active_purchase.get("purchase_id"),
        "product_name": active_purchase.get("product_name"),
        "purchase_type": active_purchase.get("purchase_type"),
    }


def preview_text(
    value: Any,
    *,
    max_chars: int = MAX_RESPONSE_PREVIEW_CHARS,
) -> str | None:
    """Return single-line bounded text."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _format_mapping(data: Mapping[str, Any], *, indent: int) -> list[str]:
    lines: list[str] = []
    for key, value in data.items():
        lines.extend(_format_value(str(key), value, indent=indent))
    return lines


def _format_value(key: str, value: Any, *, indent: int) -> list[str]:
    prefix = " " * indent
    if value is None:
        return [f"{prefix}{key}: null"]
    if isinstance(value, Mapping):
        visible_items = {item_key: item_value for item_key, item_value in value.items()}
        if not visible_items:
            return [f"{prefix}{key}: {{}}"]
        lines = [f"{prefix}{key}:"]
        lines.extend(_format_mapping(visible_items, indent=indent + 2))
        return lines
    if isinstance(value, list | tuple):
        return _format_sequence(key, value, indent=indent)
    return [f"{prefix}{key}: {value}"]


def _format_sequence(key: str, value: Sequence[Any], *, indent: int) -> list[str]:
    prefix = " " * indent
    if not value:
        return [f"{prefix}{key}: []"]
    lines = [f"{prefix}{key}:"]
    visible_items = list(value[:MAX_TRACE_ITEMS])
    for item in visible_items:
        item_prefix = " " * (indent + 2)
        if isinstance(item, Mapping):
            lines.append(f"{item_prefix}-")
            lines.extend(_format_mapping(item, indent=indent + 4))
        else:
            lines.append(f"{item_prefix}- {item}")
    remaining = len(value) - len(visible_items)
    if remaining > 0:
        lines.append(f"{' ' * (indent + 2)}... {remaining} more items not shown")
    return lines


def _tool_names(tools: Any) -> list[str]:
    if not isinstance(tools, list):
        return []
    return [
        str(tool.get("name"))
        for tool in tools
        if isinstance(tool, Mapping) and tool.get("name")
    ]


def _tool_call_names(tool_calls: Any) -> list[str]:
    if not isinstance(tool_calls, list):
        return []
    names = []
    for tool_call in tool_calls:
        if isinstance(tool_call, Mapping) and tool_call.get("name"):
            names.append(str(tool_call["name"]))
    return names


def _extract_response_context(messages: Any) -> dict[str, Any]:
    if not isinstance(messages, list):
        return {}
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content.startswith(
            "Compact conversation context"
        ):
            continue
        try:
            payload = json.loads(content.split(": ", 1)[1])
        except (IndexError, json.JSONDecodeError):
            return {}
        response_context = payload.get("response_context")
        return response_context if isinstance(response_context, dict) else {}
    return {}


def _active_scope(model_context: Mapping[str, Any]) -> Any:
    state = model_context.get("conversation_state")
    if not isinstance(state, str):
        return None
    for part in state.split(", "):
        if part.startswith("scope="):
            return part.removeprefix("scope=")
    return None


def _split_csv(value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    return [item for item in value.split(",") if item]


def _tool_for_workflow(workflow: Any) -> str | None:
    return {
        "account_fact": "get_customer_purchase_history",
        "refund_policy": "get_refund_policy",
        "refund_eligibility": "get_refund_eligibility",
    }.get(str(workflow))


def _tool_arguments(data: Mapping[str, Any]) -> dict[str, Any]:
    hidden_keys = {
        "tool_name",
        "tool_call_id",
        "model_arguments",
        "requested_tool_name",
        "reason",
    }
    return {
        key: value
        for key, value in data.items()
        if key not in hidden_keys and not key.startswith("requested_")
    }


def _purchase_items_preview(value: Any) -> list[str]:
    purchases = value if isinstance(value, list) else []
    items = [
        " | ".join(
            str(part)
            for part in (
                purchase.get("id"),
                purchase.get("product_name"),
                purchase.get("purchase_type"),
                purchase.get("amount_display"),
                purchase.get("status"),
            )
            if part is not None
        )
        for purchase in purchases[:MAX_TRACE_ITEMS]
        if isinstance(purchase, Mapping)
    ]
    remaining = len(purchases) - len(items)
    if remaining > 0:
        items.append(f"... {remaining} total not shown")
    return items


def _eligibility_items_preview(value: Any) -> list[str]:
    purchases = value if isinstance(value, list) else []
    items = []
    for purchase in purchases[:MAX_TRACE_ITEMS]:
        if not isinstance(purchase, Mapping):
            continue
        eligibility = (
            "eligible"
            if purchase.get("can_enter_refund_workflow") is True
            else "blocked"
        )
        items.append(
            " | ".join(
                str(part)
                for part in (
                    purchase.get("id"),
                    purchase.get("product_name"),
                    purchase.get("purchase_type"),
                    eligibility,
                )
                if part is not None
            )
        )
    remaining = len(purchases) - len(items)
    if remaining > 0:
        items.append(f"... {remaining} total not shown")
    return items


def _id_items_preview(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item) for item in value[:MAX_TRACE_ITEMS]]
    remaining = len(value) - len(items)
    if remaining > 0:
        items.append(f"... {remaining} more items not shown")
    return items


def _active_result_set_items_preview(value: Any) -> list[dict[str, Any] | str]:
    if not isinstance(value, list):
        return []
    preview: list[dict[str, Any] | str] = []
    for item in value[:MAX_ACTIVE_RESULT_SET_PREVIEW_ITEMS]:
        if not isinstance(item, Mapping):
            continue
        preview.append(
            {
                key: item.get(key)
                for key in (
                    "product_name",
                    "purchase_type",
                    "amount_display",
                    "status",
                    "purchased_at",
                )
                if item.get(key) is not None
            }
        )
    remaining = len(value) - len(preview)
    if remaining > 0:
        preview.append(f"... {remaining} more items not shown")
    return preview


def _summarize_eligibility_resolution(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    purchase_ids = _get_attr_or_key(value, "purchase_ids")
    return {
        "purchase_ids": list(purchase_ids) if isinstance(purchase_ids, list) else [],
        "context": _get_attr_or_key(value, "context"),
    }


def _purchase_label(value: Any) -> dict[str, Any] | None:
    purchase = _mapping_or_none(value)
    if purchase is None:
        return None
    return {
        "purchase_id": purchase.get("id") or purchase.get("purchase_id"),
        "product_name": purchase.get("product_name"),
        "purchase_type": purchase.get("purchase_type"),
    }


def _page_label(value: Any) -> str | None:
    page = _mapping_or_none(value)
    if page is None:
        return None
    surface = page.get("surface")
    purchase_id = page.get("purchase_id")
    return f"{surface}:{purchase_id}" if purchase_id else str(surface)


def _page_reference_label(value: Any) -> str | None:
    page = _mapping_or_none(value)
    if page is None:
        return None
    purchase = _mapping_or_none(page.get("purchase"))
    if purchase is None:
        return str(page.get("surface"))
    return " | ".join(
        str(part)
        for part in (
            page.get("surface"),
            purchase.get("id"),
            purchase.get("product_name"),
            purchase.get("purchase_type"),
        )
        if part is not None
    )


def _refund_context_from_state(data: Mapping[str, Any]) -> dict[str, Any]:
    active_workflow = _mapping_or_none(data.get("active_workflow")) or {}
    return {
        "selected_count": None,
        "context": active_workflow.get("operation"),
    }


def _active_workflow_kind(state: Mapping[str, Any]) -> Any:
    active_workflow = _mapping_or_none(state.get("active_workflow"))
    return active_workflow.get("kind") if active_workflow else None


def _lookup_key(object_kind: Any, operation_kind: Any) -> str | None:
    if object_kind is None or operation_kind is None:
        return None
    return f"{object_kind} + {operation_kind}"


def _object_to_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value
    return value


def _nested_attr(value: Any, parent: str, child: str) -> Any:
    parent_value = _get_attr_or_key(value, parent)
    return _get_attr_or_key(parent_value, child)


def _get_attr_or_key(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list | tuple) else 0

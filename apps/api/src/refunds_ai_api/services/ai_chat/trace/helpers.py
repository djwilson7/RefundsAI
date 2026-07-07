"""Small helpers shared by trace summarizers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

MAX_TRACE_ITEMS = 10
MAX_ACTIVE_RESULT_SET_PREVIEW_ITEMS = 5
MAX_RESPONSE_PREVIEW_CHARS = 160
MAX_MESSAGE_PREVIEW_CHARS = 240


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

def _short_id(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) < 8:
        return value if isinstance(value, str) else None
    return value[:8]

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

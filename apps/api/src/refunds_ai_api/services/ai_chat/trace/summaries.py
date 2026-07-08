"""Trace event summarizers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .helpers import (
    MAX_MESSAGE_PREVIEW_CHARS,
    MAX_RESPONSE_PREVIEW_CHARS,
    _active_result_set_items_preview,
    _active_scope,
    _active_workflow_kind,
    _count,
    _eligibility_items_preview,
    _enum_value,
    _extract_response_context,
    _get_attr_or_key,
    _lookup_key,
    _mapping_or_none,
    _nested_attr,
    _object_to_mapping,
    _page_label,
    _page_reference_label,
    _purchase_items_preview,
    _purchase_label,
    _refund_context_from_state,
    _short_id,
    _split_csv,
    _summarize_eligibility_resolution,
    _tool_arguments,
    _tool_call_names,
    _tool_for_workflow,
    _tool_names,
    preview_text,
)
from .state_summaries import (
    summarize_active_purchase,
    summarize_active_result_set,
    summarize_active_workflow,
    summarize_conversation_state,
    summarize_pending_refund_action,
)


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

def summarize_workflow_confirmation(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return confirmation gate details for a pending refund mutation."""
    pending_action = _mapping_or_none(data.get("pending_action")) or {}
    workflow = _mapping_or_none(data.get("workflow")) or {}
    return {
        "workflow": data.get("kind"),
        "reason": data.get("reason"),
        "pending_action": {
            "action": pending_action.get("action"),
            "product_name": pending_action.get("product_name"),
            "purchase_type": pending_action.get("purchase_type"),
            "required_action": pending_action.get("required_action"),
            "refundable_amount_cents": pending_action.get("refundable_amount_cents"),
        },
        "current_workflow": {
            "refund_stage": workflow.get("refund_stage"),
            "required_action": workflow.get("required_action"),
            "can_prepare_refund": workflow.get("can_prepare_refund"),
            "can_issue_funds": workflow.get("can_issue_funds"),
        },
    }

def summarize_workflow_confirmation_command(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return canonical confirmation-command boundary details."""
    pending_action = _mapping_or_none(data.get("pending_action")) or {}
    summary = {
        "workflow": data.get("kind"),
        "purchase": {
            "purchase_id": _short_id(data.get("purchase_id")),
            "purchase_type": data.get("purchase_type"),
            "active_refund_stage": data.get("active_refund_stage"),
        },
        "command": {
            "expected": data.get("expected_command"),
            "received": preview_text(data.get("received_command")),
            "matched": data.get("matched_command"),
            "confirmed": data.get("confirmed"),
            "confirmation_granted_at": data.get("confirmation_granted_at"),
        },
        "pending_action": {
            "action": pending_action.get("action"),
            "product_name": pending_action.get("product_name"),
            "purchase_id": _short_id(pending_action.get("purchase_id")),
            "purchase_type": pending_action.get("purchase_type"),
            "required_action": pending_action.get("required_action"),
        }
        if pending_action
        else None,
    }
    return summary

def summarize_workflow_mutation(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return mutation execution details without dumping full payloads."""
    result = _mapping_or_none(data.get("result"))
    summary = {
        "workflow": data.get("kind"),
        "action": data.get("action"),
        "purchase_id": _short_id(data.get("purchase_id")),
        "purchase_type": data.get("purchase_type"),
        "active_refund_stage": data.get("active_refund_stage"),
        "expected_command": data.get("expected_command"),
        "received_command": preview_text(data.get("received_command")),
        "matched_command": data.get("matched_command"),
        "product_name": data.get("product_name"),
        "reason": data.get("reason"),
        "expected_transition": data.get("expected_transition"),
    }
    if result is not None:
        summary["result"] = {
            "refund_stage": result.get("refund_stage"),
            "required_action": result.get("required_action"),
            "refundable_amount_cents": result.get("refundable_amount_cents"),
            "refund_outcome": result.get("refund_outcome"),
        }
    return summary

def summarize_refund_mutation_lifecycle(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return grouped refund mutation lifecycle details."""
    purchase = _mapping_or_none(data.get("purchase")) or {}
    confirmation = _mapping_or_none(data.get("confirmation")) or {}
    result = _mapping_or_none(data.get("result")) or {}
    transitions = data.get("transitions")
    safe_transitions: list[dict[str, Any]] = []
    if isinstance(transitions, list):
        for transition in transitions:
            transition_data = _mapping_or_none(transition) or {}
            transition_result = _mapping_or_none(transition_data.get("result")) or {}
            permission = _mapping_or_none(transition_data.get("permission")) or {}
            safe_transitions.append(
                {
                    "action": transition_data.get("action"),
                    "from_stage": transition_data.get("from_stage"),
                    "expected_stage": transition_data.get("expected_stage"),
                    "persisted_stage": transition_data.get("persisted_stage"),
                    "validation": transition_data.get("validation"),
                    "required_action_before": transition_data.get(
                        "required_action_before"
                    ),
                    "required_action_after": transition_data.get(
                        "required_action_after"
                    ),
                    "permission": {
                        "can_prepare_refund": permission.get("can_prepare_refund"),
                        "can_issue_funds": permission.get("can_issue_funds"),
                        "validated": permission.get("validated"),
                    },
                    "result": {
                        "refund_stage": transition_result.get("refund_stage"),
                        "required_action": transition_result.get("required_action"),
                        "refundable_amount_cents": transition_result.get(
                            "refundable_amount_cents"
                        ),
                        "refund_outcome": transition_result.get("refund_outcome"),
                    },
                }
            )

    return {
        "purchase": {
            "purchase_id": _short_id(purchase.get("purchase_id")),
            "product_name": purchase.get("product_name"),
            "purchase_type": purchase.get("purchase_type"),
        },
        "confirmation": {
            "expected": confirmation.get("expected"),
            "received": preview_text(confirmation.get("received")),
            "persisted_granted": confirmation.get("persisted_granted"),
            "matched": confirmation.get("matched"),
            "granted_at": confirmation.get("granted_at"),
            "consumed_at": confirmation.get("consumed_at"),
            "consumed_by_action": confirmation.get("consumed_by_action"),
        },
        "transitions": safe_transitions,
        "result": {
            "final_stage": result.get("final_stage"),
            "required_action": result.get("required_action"),
            "refundable_amount_cents": result.get("refundable_amount_cents"),
            "refund_outcome": result.get("refund_outcome"),
        },
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
        history_summary = (
            result.get("history_summary")
            if isinstance(result.get("history_summary"), Mapping)
            else {}
        )
        total_count = history_summary.get(
            "total_purchase_count",
            aggregates.get("total_purchase_count", 0),
        )
        purchases = result.get("purchases")
        return {
            "summary": (
                f"{total_count} purchases, "
                f"${aggregates.get('total_amount_dollars', '0.00')}"
            ),
            "aggregates": {
                "total_purchase_count": aggregates.get("total_purchase_count"),
                "total_spend": f"${aggregates.get('total_amount_dollars', '0.00')}",
            },
            "history_summary": {
                "total_purchase_count": history_summary.get("total_purchase_count"),
                "non_refunded_purchase_count": history_summary.get(
                    "non_refunded_purchase_count"
                ),
                "refunded_purchase_count": history_summary.get(
                    "refunded_purchase_count"
                ),
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
    if "refund_stage" in result:
        return {
            "summary": (
                f"refund {result.get('refund_stage')}, "
                f"next={result.get('required_action')}"
            ),
            "result": {
                "refund_stage": result.get("refund_stage"),
                "required_action": result.get("required_action"),
                "refund_outcome": result.get("refund_outcome"),
                "refundable_amount_cents": result.get("refundable_amount_cents"),
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
        "pending_refund_action": summarize_pending_refund_action(
            data.get("pending_refund_action")
        ),
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
            "pending_refund_action": summarize_pending_refund_action(
                state.get("pending_refund_action")
            ),
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

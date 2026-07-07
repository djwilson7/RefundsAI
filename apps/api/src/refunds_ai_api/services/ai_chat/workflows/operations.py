"""Requested operation resolution for deterministic chat workflows."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from refunds_ai_api.services.ai_chat.workflow import (
    parse_refund_workflow_continuation_intent,
    parse_refund_workflow_mutation_intent,
)


class WorkflowOperation(StrEnum):
    """Action the user wants to perform on the resolved conversation object."""

    COUNT = "count"
    LIST = "list"
    SELECT_FIRST = "select_first"
    SELECT_LAST = "select_last"
    SELECT_LATEST = "select_latest"
    SELECT_PREVIOUS = "select_previous"
    POLICY = "policy"
    ELIGIBILITY = "eligibility"
    START_REFUND = "start_refund"
    EXPLAIN = "explain"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OperationResolution:
    """Resolved user operation plus trace metadata."""

    operation: WorkflowOperation
    confidence: Literal["deterministic", "model_assisted", "fallback"]
    reason: str


def resolve_operation(
    message: str,
    *,
    conversation_state: Mapping[str, Any] | None,
    model_intent: Mapping[str, Any] | None = None,
) -> OperationResolution:
    """Resolve the requested operation for workflow lookup."""
    normalized_message = message.casefold()

    if _has_refund_start_operation(normalized_message, conversation_state):
        return OperationResolution(
            WorkflowOperation.START_REFUND,
            "deterministic",
            "refund_start_operation",
        )

    if _has_policy_to_eligibility_follow_up(normalized_message, conversation_state):
        return OperationResolution(
            WorkflowOperation.ELIGIBILITY,
            "deterministic",
            "policy_follow_up_confirmation_promoted",
        )

    if _has_refund_denial_explanation_operation(
        normalized_message,
        conversation_state,
    ):
        return OperationResolution(
            WorkflowOperation.ELIGIBILITY,
            "deterministic",
            "refund_denial_explanation_phrase_matched",
        )

    if _has_refund_eligibility_operation(normalized_message):
        return OperationResolution(
            WorkflowOperation.ELIGIBILITY,
            "deterministic",
            "refund_eligibility_phrase_matched",
        )

    if _has_refund_policy_operation(normalized_message):
        return OperationResolution(
            WorkflowOperation.POLICY,
            "deterministic",
            "refund_policy_phrase_matched",
        )

    if re.search(r"\b(?:first|oldest|earliest)\b", normalized_message):
        return OperationResolution(
            WorkflowOperation.SELECT_FIRST,
            "deterministic",
            "select_first_operation",
        )
    if re.search(r"\b(?:last)\b", normalized_message):
        return OperationResolution(
            WorkflowOperation.SELECT_LAST,
            "deterministic",
            "select_last_operation",
        )
    if re.search(r"\b(?:latest|newest|most\s+recent)\b", normalized_message):
        return OperationResolution(
            WorkflowOperation.SELECT_LATEST,
            "deterministic",
            "select_latest_operation",
        )
    if re.search(r"\b(?:previous|prior)\b", normalized_message):
        return OperationResolution(
            WorkflowOperation.SELECT_PREVIOUS,
            "deterministic",
            "select_previous_operation",
        )

    if _has_list_operation(normalized_message):
        return OperationResolution(
            WorkflowOperation.LIST,
            "deterministic",
            "list_operation",
        )

    if _has_count_operation(normalized_message):
        return OperationResolution(
            WorkflowOperation.COUNT,
            "deterministic",
            "count_operation",
        )

    if _has_explain_operation(normalized_message):
        return OperationResolution(
            WorkflowOperation.EXPLAIN,
            "deterministic",
            "explain_operation",
        )

    model_tool_name = _first_model_tool_name(model_intent)
    if model_tool_name == "get_refund_eligibility":
        return OperationResolution(
            WorkflowOperation.ELIGIBILITY,
            "model_assisted",
            "model_requested_refund_eligibility_tool",
        )
    if model_tool_name == "get_refund_policy":
        return OperationResolution(
            WorkflowOperation.POLICY,
            "model_assisted",
            "model_requested_refund_policy_tool",
        )
    if model_tool_name in {
        "get_customer_purchase_history",
        "get_purchase_count_by_amount_threshold",
        "get_purchase_history_by_date_range",
    }:
        return OperationResolution(
            WorkflowOperation.LIST,
            "model_assisted",
            "model_requested_account_fact_tool",
        )

    return OperationResolution(
        WorkflowOperation.UNKNOWN,
        "fallback",
        "unknown_operation",
    )


def _has_refund_start_operation(
    message: str,
    conversation_state: Mapping[str, Any] | None,
) -> bool:
    if parse_refund_workflow_continuation_intent(message) is not None:
        return True
    if parse_refund_workflow_mutation_intent(message) is not None:
        return True

    continuation_patterns = (
        r"^\s*(?:let'?s|lets)\s+do\s+that\s*[.!?]*\s*$",
        r"^\s*do\s+it\s*[.!?]*\s*$",
        r"^\s*go\s+ahead\s*[.!?]*\s*$",
        r"^\s*yes,?\s+(?:do\s+it|go\s+ahead)\s*[.!?]*\s*$",
    )
    if not any(re.search(pattern, message) for pattern in continuation_patterns):
        return False

    active_workflow = (
        conversation_state.get("active_workflow")
        if isinstance(conversation_state, Mapping)
        else None
    )
    if not isinstance(active_workflow, Mapping):
        return True
    return active_workflow.get("kind") in {"refund_eligibility", "refund_policy"}


def _has_refund_eligibility_operation(message: str) -> bool:
    eligibility_patterns = (
        r"\bcan\s+i\s+refund\b",
        r"\bcan\s+i\s+get\s+a\s+refund\s+for\b",
        r"\bcould\s+i\s+refund\b",
        r"\bam\s+i\s+able\s+to\s+refund\b",
        r"\bam\s+i\s+able\s+to\s+get\s+a\s+refund\s+for\b",
        r"\bam\s+i\s+eligible\b",
        r"\bis\b.+\beligible\s+for\s+(?:a\s+)?refund\b",
        r"\bis\s+(?:it|this|that|this\s+item|that\s+item)\s+eligible\b",
        r"\bis\s+(?:it|this|that|this\s+item|that\s+item)\s+refund(?:ed|able)\b",
        r"\bis\b.+\brefund(?:ed|able)\b",
        r"\bare\s+(?:they|these|those|them)\s+refund(?:ed|able)\b",
        r"\bcan\s+(?:they|these|those|them)\s+be\s+refund(?:ed|able)\b",
        r"\bcan\b.+\bbe\s+refund(?:ed|able)\b",
        r"\bcheck\s+if\b.+\brefund(?:ed|able)\b",
        r"\beligib(?:le|ility)\b",
        r"\brefund\s+eligibility\b",
    )
    return any(re.search(pattern, message) for pattern in eligibility_patterns)


def _has_refund_denial_explanation_operation(
    message: str,
    conversation_state: Mapping[str, Any] | None,
) -> bool:
    explanation_patterns = (
        r"\bwhy\s+can'?t\s+i\s+get\s+a\s+refund\b",
        r"\bwhy\s+is\s+(?:it|this|that|this\s+item|that\s+item)\s+not\s+eligible\b",
        r"\bwhy\s+was\s+(?:it|this|that|this\s+item|that\s+item)\s+blocked\b",
        r"\bwhat'?s\s+stopping\s+the\s+refund\b",
        r"\bwhat\s+is\s+stopping\s+the\s+refund\b",
        r"\bwhy\s+can'?t\s+(?:it|this|that|this\s+item|that\s+item)\s+be\s+refunded\b",
        r"\bwhy\s+is\s+(?:it|this|that|this\s+item|that\s+item)\s+not\s+refund(?:ed|able)\b",
    )
    if not any(re.search(pattern, message) for pattern in explanation_patterns):
        return False
    if not isinstance(conversation_state, Mapping):
        return True
    active_workflow = conversation_state.get("active_workflow")
    if isinstance(active_workflow, Mapping) and active_workflow.get("kind") in {
        "refund_eligibility",
        "refund_mutation",
    }:
        return True
    return isinstance(conversation_state.get("active_refund_context"), Mapping)


def _has_policy_to_eligibility_follow_up(
    message: str,
    conversation_state: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(conversation_state, Mapping):
        return False
    active_workflow = conversation_state.get("active_workflow")
    if not isinstance(active_workflow, Mapping):
        return False
    if active_workflow.get("kind") != "refund_policy":
        return False
    if not _has_active_purchase_or_result_set(conversation_state):
        return False

    follow_up_patterns = (
        r"^yes[.!]?$",
        r"^yes,?\s+please[.!]?$",
        r"^yes,?\s+(?:please,?\s+)?(?:let'?s|lets)\s+check[.!]?$",
        r"^(?:let'?s|lets)\s+check[.!]?$",
        r"^check\s+(?:it|that|them|those|these)[.!]?$",
    )
    return any(re.search(pattern, message) for pattern in follow_up_patterns)


def _has_active_purchase_or_result_set(
    conversation_state: Mapping[str, Any],
) -> bool:
    active_result_set = conversation_state.get("active_result_set")
    if isinstance(active_result_set, Mapping) and active_result_set.get("purchase_ids"):
        return True
    active_purchase = conversation_state.get("active_purchase")
    if isinstance(active_purchase, Mapping) and active_purchase.get("purchase_id"):
        return True
    return bool(conversation_state.get("selected_purchase_id"))


def _has_refund_policy_operation(message: str) -> bool:
    return any(
        term in message
        for term in (
            "policy",
            "policies",
            "return policy",
            "refund policy",
            "rule",
            "rules",
            "guideline",
            "guidelines",
            "requirement",
            "requirements",
            "window",
        )
    )


def _has_list_operation(message: str) -> bool:
    return any(
        re.search(pattern, message)
        for pattern in (
            r"\blist\b",
            r"\bshow\b",
            r"\bwhat\s+are\s+they\b",
            r"\bwhich\s+ones\b",
            r"\bwhat\s+are\s+those\b",
            r"\bwhat\s+are\s+these\b",
        )
    )


def _has_count_operation(message: str) -> bool:
    return any(
        term in message
        for term in (
            "how many",
            "count",
            "number of",
            "total number",
        )
    )


def _has_explain_operation(message: str) -> bool:
    return any(
        term in message
        for term in (
            "why",
            "explain",
            "details",
            "detail",
            "summarize",
            "summary",
        )
    )


def _first_model_tool_name(model_intent: Mapping[str, Any] | None) -> str | None:
    if not isinstance(model_intent, Mapping):
        return None
    tool_calls = model_intent.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return None
    first_tool_call = tool_calls[0]
    if isinstance(first_tool_call, Mapping):
        name = first_tool_call.get("name")
        return name if isinstance(name, str) else None
    return getattr(first_tool_call, "name", None)

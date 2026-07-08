"""Workflow classification for deterministic AI chat routing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from refunds_ai_api.services.ai_chat.dates import parse_date_range_query
from refunds_ai_api.services.ai_chat.entity_extraction import extract_entity
from refunds_ai_api.services.ai_chat.parsing import parse_amount_threshold_query
from refunds_ai_api.services.ai_chat.routing import (
    has_account_fact_intent,
    has_context_reference,
    has_policy_follow_up_intent,
    has_refund_eligibility_intent,
    parse_refund_policy_query,
)
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflow import (
    is_generic_refund_confirmation_reply,
    is_refund_confirmation_boundary_reply,
    parse_refund_workflow_confirmation_intent,
    parse_refund_workflow_continuation_intent,
    parse_refund_workflow_decline_intent,
    parse_refund_workflow_mutation_intent,
)
from refunds_ai_api.services.ai_chat.workflows.classification_types import WorkflowKind
from refunds_ai_api.services.ai_chat.workflows.lookup import lookup_workflow_kind
from refunds_ai_api.services.ai_chat.workflows.objects import (
    ConversationObject,
    ConversationObjectKind,
    resolve_conversation_object,
)
from refunds_ai_api.services.ai_chat.workflows.operations import (
    OperationResolution,
    WorkflowOperation,
    resolve_operation,
)


@dataclass(frozen=True)
class WorkflowClassification:
    """Workflow selected before backend tool execution."""

    kind: WorkflowKind
    confidence: Literal["deterministic", "model_assisted", "fallback"]
    reason: str
    conversation_object: ConversationObject | None = None
    operation: OperationResolution | None = None


def normalize_input_text(text: str) -> str:
    """Normalize casing, punctuation, spelling, plurals, and common aliases."""
    if not text:
        return ""
    # Casing
    text = text.lower().strip()
    # Punctuation (remove common punctuation but keep spaces)
    import re
    text = re.sub(r'[^\w\s\-\:\>]', '', text)
    # Common spelling corrections / aliases / shorthand
    alias_map = {
        "puchase": "purchase",
        "puchases": "purchases",
        "purhcase": "purchase",
        "purhcases": "purchases",
        "purches": "purchase",
        "purcheses": "purchases",
        "refun": "refund",
        "refnd": "refund",
        "subscritpion": "subscription",
        "subscritpions": "subscriptions",
        "subs": "subscriptions",
        "sub": "subscription",
        "orde": "order",
        "orderes": "orders",
        "physicall": "physical",
        "digitall": "digital",
        "cancle": "cancel",
        "cancell": "cancel",
        "canceling": "cancelling",
        "retur": "return",
        "retrn": "return",
        "retrns": "returns",
        "shiping": "shipping",
        "shippment": "shipment",
        "shippments": "shipments",
    }
    words = text.split()
    normalized_words = []
    for word in words:
        corrected = alias_map.get(word, word)
        # Map specific common plurals:
        plural_map = {
            "purchases": "purchase",
            "subscriptions": "subscription",
            "orders": "order",
            "refunds": "refund",
            "returns": "return",
            "shipments": "shipment",
        }
        corrected = plural_map.get(corrected, corrected)
        normalized_words.append(corrected)
    return " ".join(normalized_words)


def classify_workflow(
    message: str,
    *,
    conversation_state: Mapping[str, Any] | None,
    page_context: Mapping[str, Any] | None,
    model_intent: Mapping[str, Any] | None = None,
) -> WorkflowClassification:
    """Classify a user message into the deterministic workflow to execute."""
    normalized_message = normalize_input_text(message)
    normalized_state = normalize_conversation_state(
        dict(conversation_state) if conversation_state is not None else None
    )
    conversation_object = resolve_conversation_object(
        message,
        conversation_state=normalized_state,
        page_context=page_context,
    )
    operation = resolve_operation(
        normalized_message,
        conversation_state=normalized_state,
        model_intent=model_intent,
    )
    workflow_kind = lookup_workflow_kind(conversation_object, operation.operation)
    active_refund_context = normalized_state.get("active_refund_context")
    if (
        normalized_state.get("pending_refund_action") is None
        and normalized_state.get("last_completed_refund") is not None
        and is_generic_refund_confirmation_reply(normalized_message)
    ):
        return WorkflowClassification(
            WorkflowKind.REFUND_MUTATION,
            "deterministic",
            "ambiguous_affirmation_after_completed_refund",
            conversation_object,
            operation,
        )
    if (
        isinstance(active_refund_context, dict)
        and active_refund_context.get("confirmation_command")
        and is_refund_confirmation_boundary_reply(message)
    ):
        return WorkflowClassification(
            WorkflowKind.REFUND_MUTATION,
            "deterministic",
            "refund_confirmation_command_boundary",
            conversation_object,
            operation,
        )
    if (
        normalized_state.get("pending_refund_action") is not None
        and (
            parse_refund_workflow_confirmation_intent(normalized_message)
            or parse_refund_workflow_decline_intent(normalized_message)
        )
    ):
        return WorkflowClassification(
            WorkflowKind.REFUND_MUTATION,
            "deterministic",
            "pending_refund_action_confirmation",
            conversation_object,
            operation,
        )

    entity_extraction = extract_entity(message)
    if (
        entity_extraction.intent == "refund_mutation"
        and normalized_message.startswith(
            ("refund ", "return ", "i want to refund ", "i want to return ")
        )
        and entity_extraction.entity_kind
        in {
            "named_product",
            "purchase_id",
            "sku",
            "contextual_reference",
            "purchase_type",
            "none",
        }
    ):
        return WorkflowClassification(
            WorkflowKind.REFUND_MUTATION,
            "deterministic",
            "explicit_refund_action",
            conversation_object,
            operation,
        )

    if workflow_kind is not WorkflowKind.OFF_DOMAIN:
        return WorkflowClassification(
            workflow_kind,
            operation.confidence,
            _classification_reason(conversation_object, operation),
            conversation_object,
            operation,
        )

    if parse_refund_workflow_continuation_intent(normalized_message) is not None:
        return WorkflowClassification(
            WorkflowKind.REFUND_MUTATION,
            "deterministic",
            "refund_workflow_continuation_intent",
            conversation_object,
            operation,
        )

    if parse_refund_workflow_mutation_intent(normalized_message) is not None:
        return WorkflowClassification(
            WorkflowKind.REFUND_MUTATION,
            "deterministic",
            "refund_workflow_mutation_intent",
            conversation_object,
            operation,
        )

    if has_refund_eligibility_intent(
        normalized_message,
        conversation_state=normalized_state,
    ):
        return WorkflowClassification(
            WorkflowKind.REFUND_ELIGIBILITY,
            "deterministic",
            "refund_eligibility_intent",
            conversation_object,
            operation,
        )

    policy_query = parse_refund_policy_query(
        normalized_message,
        conversation_state=normalized_state,
    )
    if policy_query is not None:
        return WorkflowClassification(
            WorkflowKind.REFUND_POLICY,
            "deterministic",
            "refund_policy_intent",
            conversation_object,
            operation,
        )

    if has_policy_follow_up_intent(normalized_message, normalized_state):
        return WorkflowClassification(
            WorkflowKind.REFUND_POLICY,
            "deterministic",
            "refund_policy_follow_up_intent",
            conversation_object,
            operation,
        )

    if parse_amount_threshold_query(normalized_message) is not None:
        return WorkflowClassification(
            WorkflowKind.ACCOUNT_FACT,
            "deterministic",
            "amount_threshold_intent",
            conversation_object,
            operation,
        )

    if parse_date_range_query(normalized_message) is not None:
        return WorkflowClassification(
            WorkflowKind.ACCOUNT_FACT,
            "deterministic",
            "date_range_intent",
            conversation_object,
            operation,
        )

    if has_account_fact_intent(normalized_message):
        return WorkflowClassification(
            WorkflowKind.ACCOUNT_FACT,
            "deterministic",
            "account_fact_intent",
            conversation_object,
            operation,
        )

    if _has_follow_up_purchase_context(normalized_message, normalized_state):
        return WorkflowClassification(
            WorkflowKind.ACCOUNT_FACT,
            "deterministic",
            "active_result_set_follow_up",
            conversation_object,
            operation,
        )

    model_tool_name = _first_model_tool_name(model_intent)
    if model_tool_name == "get_refund_eligibility":
        return WorkflowClassification(
            WorkflowKind.REFUND_ELIGIBILITY,
            "model_assisted",
            "model_requested_refund_eligibility_tool",
            conversation_object,
            operation,
        )
    if model_tool_name == "get_refund_policy":
        return WorkflowClassification(
            WorkflowKind.REFUND_POLICY,
            "model_assisted",
            "model_requested_refund_policy_tool",
            conversation_object,
            operation,
        )
    if model_tool_name in {
        "get_customer_purchase_history",
        "get_purchase_count_by_amount_threshold",
        "get_purchase_history_by_date_range",
    }:
        return WorkflowClassification(
            WorkflowKind.ACCOUNT_FACT,
            "model_assisted",
            "model_requested_account_fact_tool",
            conversation_object,
            operation,
        )

    return WorkflowClassification(
        WorkflowKind.OFF_DOMAIN,
        "fallback",
        "off_domain_fallback",
        conversation_object,
        operation,
    )


def _classification_reason(
    conversation_object: ConversationObject,
    operation: OperationResolution,
) -> str:
    """Return stable routing reason labels for object-operation matches."""
    if (
        conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET
        and operation.operation is WorkflowOperation.ELIGIBILITY
    ):
        return "active_result_set_refund_query"
    if (
        conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET
        and operation.operation is WorkflowOperation.POLICY
    ):
        return "active_result_set_policy"
    if (
        conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET
        and operation.operation is WorkflowOperation.START_REFUND
    ):
        return "active_result_set_refund_mutation"
    if conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET:
        return "active_result_set_follow_up"
    return f"{conversation_object.kind.value}_{operation.operation.value}"


def _has_follow_up_purchase_context(
    message: str,
    conversation_state: Mapping[str, Any],
) -> bool:
    """Return whether a vague follow-up can be grounded to active purchase context."""
    if not has_context_reference(message.casefold()):
        return False
    active_result_set = conversation_state.get("active_result_set")
    if isinstance(active_result_set, Mapping) and active_result_set.get("purchase_ids"):
        return True
    if conversation_state.get("selected_purchase_ids"):
        return True
    active_purchase = conversation_state.get("active_purchase")
    if isinstance(active_purchase, Mapping) and active_purchase.get("purchase_id"):
        return True
    return bool(conversation_state.get("selected_purchase_id"))


def _first_model_tool_name(model_intent: Mapping[str, Any] | None) -> str | None:
    """Return the first requested model tool name from compact model intent."""
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

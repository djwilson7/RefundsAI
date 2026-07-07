"""Workflow-scoped context resolution for AI chat orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_date_range_query
from refunds_ai_api.services.ai_chat.models import ChatGraphState, EligibilityResolution
from refunds_ai_api.services.ai_chat.parsing import parse_amount_threshold_query
from refunds_ai_api.services.ai_chat.resolution import (
    resolve_page_reference,
    resolve_purchase_by_id,
    resolve_purchase_fact_context,
    resolve_refund_eligibility_query,
    resolve_refund_policy_query_with_purchase,
)
from refunds_ai_api.services.ai_chat.routing import has_account_fact_intent
from refunds_ai_api.services.ai_chat.workflow import (
    parse_refund_workflow_continuation_intent,
    parse_refund_workflow_mutation_intent,
)
from refunds_ai_api.services.ai_chat.workflows.classification import (
    WorkflowClassification,
    WorkflowKind,
)
from refunds_ai_api.services.ai_chat.workflows.objects import ConversationObjectKind


@dataclass(frozen=True)
class WorkflowContext:
    """Backend-resolved context used by one deterministic chat workflow."""

    kind: WorkflowKind
    customer_id: str | None
    page_reference: dict[str, Any] | None = None
    threshold_query: dict[str, Any] | None = None
    date_range_query: dict[str, Any] | None = None
    policy_lookup_query: dict[str, Any] | None = None
    eligibility_resolution: EligibilityResolution | None = None
    resolved_purchase: dict[str, Any] | None = None
    resolved_context_purchase: dict[str, Any] | None = None
    unresolved_product_reference: str | None = None
    account_fact_intent: bool = False
    blocked_refund_intent: str | None = None
    workflow_continuation_intent: str | None = None
    classification: WorkflowClassification | None = None

    def as_legacy_context(self) -> dict[str, Any]:
        """Return the dict shape expected by older execution helpers."""
        return {
            "customer_id": self.customer_id,
            "threshold_query": self.threshold_query,
            "date_range_query": self.date_range_query,
            "policy_lookup_query": self.policy_lookup_query,
            "eligibility_resolution": self.eligibility_resolution,
            "resolved_purchase": self.resolved_purchase,
            "resolved_context_purchase": self.resolved_context_purchase,
            "unresolved_product_reference": self.unresolved_product_reference,
            "page_reference": self.page_reference,
            "blocked_refund_intent": self.blocked_refund_intent,
            "workflow_continuation_intent": self.workflow_continuation_intent,
        }


def resolve_workflow_context(
    runtime: Any,
    state: ChatGraphState,
    classification: WorkflowClassification,
) -> WorkflowContext:
    """Resolve authoritative backend context for the classified workflow."""
    customer_id = state.get("customer_id")
    message = state["message"]
    page_reference = resolve_page_reference(
        runtime.application_service,
        customer_id,
        state.get("page_context"),
    )

    threshold_query = parse_amount_threshold_query(message)
    date_range_query = parse_date_range_query(message)
    policy_lookup_query: dict[str, Any] | None = None
    resolved_purchase: dict[str, Any] | None = None
    policy_unresolved_reference: str | None = None
    eligibility_resolution: EligibilityResolution | None = None
    resolved_context_purchase: dict[str, Any] | None = None

    if classification.kind is WorkflowKind.REFUND_POLICY:
        (
            policy_lookup_query,
            resolved_purchase,
            policy_unresolved_reference,
        ) = resolve_refund_policy_query_with_purchase(
            message,
            conversation_state=state.get("conversation_state"),
            page_context=state.get("page_context"),
            application_service=runtime.application_service,
            customer_id=customer_id,
        )
        if policy_lookup_query is None:
            policy_lookup_query, resolved_purchase = _resolve_policy_from_object(
                runtime,
                customer_id,
                classification,
            )
            if policy_lookup_query is not None:
                policy_unresolved_reference = None

    if classification.kind in {
        WorkflowKind.REFUND_ELIGIBILITY,
        WorkflowKind.REFUND_MUTATION,
    }:
        eligibility_resolution = resolve_refund_eligibility_query(
            message,
            conversation_state=state.get("conversation_state"),
            page_context=state.get("page_context"),
            application_service=runtime.application_service,
            customer_id=customer_id,
        )
        if eligibility_resolution is None:
            eligibility_resolution = _resolve_eligibility_from_object(
                runtime,
                customer_id,
                classification,
            )

    if classification.kind in {
        WorkflowKind.ACCOUNT_FACT,
        WorkflowKind.REFUND_POLICY,
        WorkflowKind.REFUND_ELIGIBILITY,
        WorkflowKind.REFUND_MUTATION,
    }:
        resolved_context_purchase = resolve_purchase_fact_context(
            runtime.application_service,
            customer_id,
            message,
            state.get("conversation_state"),
            state.get("page_context"),
        )

    unresolved_product_reference = policy_unresolved_reference
    if (
        eligibility_resolution is not None
        and eligibility_resolution.unresolved_product_reference is not None
    ):
        unresolved_product_reference = eligibility_resolution.unresolved_product_reference

    workflow_continuation_intent = parse_refund_workflow_continuation_intent(message)
    blocked_refund_intent = (
        workflow_continuation_intent
        or parse_refund_workflow_mutation_intent(message)
    )

    return WorkflowContext(
        kind=classification.kind,
        customer_id=customer_id,
        page_reference=page_reference,
        threshold_query=threshold_query,
        date_range_query=date_range_query,
        policy_lookup_query=policy_lookup_query,
        eligibility_resolution=eligibility_resolution,
        resolved_purchase=resolved_purchase
        or (
            eligibility_resolution.resolved_purchase
            if eligibility_resolution is not None
            else None
        ),
        resolved_context_purchase=resolved_context_purchase,
        unresolved_product_reference=unresolved_product_reference,
        account_fact_intent=classification.kind is WorkflowKind.ACCOUNT_FACT
        or has_account_fact_intent(message)
        or resolved_context_purchase is not None,
        blocked_refund_intent=blocked_refund_intent,
        workflow_continuation_intent=workflow_continuation_intent,
        classification=classification,
    )


def _resolve_eligibility_from_object(
    runtime: Any,
    customer_id: str | None,
    classification: WorkflowClassification,
) -> EligibilityResolution | None:
    """Build eligibility arguments directly from the resolved object."""
    conversation_object = classification.conversation_object
    if conversation_object is None:
        return None
    if runtime.application_service is None or customer_id is None:
        return EligibilityResolution([], "customer_context_required")

    if conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET:
        return EligibilityResolution(
            list(conversation_object.purchase_ids),
            "selected_set",
        )

    if conversation_object.kind is ConversationObjectKind.ACTIVE_PURCHASE:
        purchase_id = conversation_object.purchase_ids[0]
        return EligibilityResolution(
            [purchase_id],
            "selected_purchase",
            resolved_purchase=resolve_purchase_by_id(
                runtime.application_service,
                customer_id,
                purchase_id,
            ),
        )

    if conversation_object.kind is ConversationObjectKind.PAGE_PURCHASE:
        purchase_id = conversation_object.purchase_ids[0]
        return EligibilityResolution(
            [purchase_id],
            "current_page",
            resolved_purchase=resolve_purchase_by_id(
                runtime.application_service,
                customer_id,
                purchase_id,
            ),
        )

    if conversation_object.kind is ConversationObjectKind.PURCHASE_TYPE:
        purchase_ids = [
            str(purchase["id"])
            for purchase in runtime.application_service.list_user_purchases(customer_id)
            if purchase.get("purchase_type") == conversation_object.purchase_type
            and isinstance(purchase.get("id"), str)
        ]
        return EligibilityResolution(
            purchase_ids,
            conversation_object.purchase_type or "purchase_type",
        )

    if conversation_object.kind is ConversationObjectKind.FULL_PURCHASE_HISTORY:
        purchase_ids = [
            str(purchase["id"])
            for purchase in runtime.application_service.list_user_purchases(customer_id)
            if isinstance(purchase.get("id"), str)
        ]
        return EligibilityResolution(purchase_ids, "all_purchases")

    return None


def _resolve_policy_from_object(
    runtime: Any,
    customer_id: str | None,
    classification: WorkflowClassification,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Build policy arguments directly from the resolved object."""
    conversation_object = classification.conversation_object
    if conversation_object is None:
        return None, None

    if conversation_object.purchase_type in {"digital", "physical", "subscription"}:
        return (
            {
                "scope": "product_type",
                "purchase_type": conversation_object.purchase_type,
            },
            None,
        )

    if (
        conversation_object.kind
        in {ConversationObjectKind.ACTIVE_PURCHASE, ConversationObjectKind.PAGE_PURCHASE}
        and conversation_object.purchase_ids
        and runtime.application_service is not None
        and customer_id is not None
    ):
        resolved_purchase = resolve_purchase_by_id(
            runtime.application_service,
            customer_id,
            conversation_object.purchase_ids[0],
        )
        if resolved_purchase is not None:
            return (
                {
                    "scope": "product_type",
                    "purchase_type": resolved_purchase["purchase_type"],
                },
                resolved_purchase,
            )

    if conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET:
        return {"scope": "general", "purchase_type": None}, None

    return None, None

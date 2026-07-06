"""Workflow lookup table for conversation object and operation pairs."""

from __future__ import annotations

from refunds_ai_api.services.ai_chat.workflows.classification_types import WorkflowKind
from refunds_ai_api.services.ai_chat.workflows.objects import (
    ConversationObject,
)
from refunds_ai_api.services.ai_chat.workflows.objects import (
    ConversationObjectKind as ObjectKind,
)
from refunds_ai_api.services.ai_chat.workflows.operations import WorkflowOperation

ACCOUNT_FACT_OPERATIONS = {
    WorkflowOperation.COUNT,
    WorkflowOperation.LIST,
    WorkflowOperation.SELECT_FIRST,
    WorkflowOperation.SELECT_LAST,
    WorkflowOperation.SELECT_LATEST,
    WorkflowOperation.SELECT_PREVIOUS,
    WorkflowOperation.EXPLAIN,
}


def lookup_workflow_kind(
    conversation_object: ConversationObject,
    operation: WorkflowOperation,
) -> WorkflowKind:
    """Return the workflow selected by deterministic object-operation lookup."""
    object_kind = conversation_object.kind

    if operation is WorkflowOperation.UNKNOWN:
        return WorkflowKind.OFF_DOMAIN

    if operation is WorkflowOperation.START_REFUND:
        if object_kind in {
            ObjectKind.ACTIVE_PURCHASE,
            ObjectKind.PAGE_PURCHASE,
            ObjectKind.PRODUCT_REFERENCE,
            ObjectKind.ACTIVE_RESULT_SET,
            ObjectKind.PURCHASE_TYPE,
        }:
            return WorkflowKind.REFUND_MUTATION
        return WorkflowKind.OFF_DOMAIN

    if operation is WorkflowOperation.ELIGIBILITY:
        if object_kind in {
            ObjectKind.ACTIVE_PURCHASE,
            ObjectKind.PAGE_PURCHASE,
            ObjectKind.PRODUCT_REFERENCE,
            ObjectKind.PURCHASE_TYPE,
            ObjectKind.ACTIVE_RESULT_SET,
            ObjectKind.DATE_RANGE,
            ObjectKind.FULL_PURCHASE_HISTORY,
        }:
            return WorkflowKind.REFUND_ELIGIBILITY
        return WorkflowKind.OFF_DOMAIN

    if operation is WorkflowOperation.POLICY:
        if object_kind in {
            ObjectKind.ACTIVE_PURCHASE,
            ObjectKind.PAGE_PURCHASE,
            ObjectKind.PRODUCT_REFERENCE,
            ObjectKind.PURCHASE_TYPE,
            ObjectKind.ACTIVE_RESULT_SET,
        }:
            return WorkflowKind.REFUND_POLICY
        return WorkflowKind.OFF_DOMAIN

    if operation in ACCOUNT_FACT_OPERATIONS:
        if object_kind in {
            ObjectKind.FULL_PURCHASE_HISTORY,
            ObjectKind.ACTIVE_RESULT_SET,
            ObjectKind.ACTIVE_PURCHASE,
            ObjectKind.PAGE_PURCHASE,
            ObjectKind.PURCHASE_TYPE,
            ObjectKind.DATE_RANGE,
            ObjectKind.AMOUNT_THRESHOLD,
        }:
            return WorkflowKind.ACCOUNT_FACT

    return WorkflowKind.OFF_DOMAIN

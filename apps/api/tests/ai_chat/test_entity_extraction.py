from __future__ import annotations

import pytest

from refunds_ai_api.services.ai_chat import AIChatService
from refunds_ai_api.services.ai_chat.entity_extraction import extract_entity
from refunds_ai_api.services.ai_chat.resolvers import eligibility as eligibility_resolver
from refunds_ai_api.services.ai_chat.workflows import context as workflow_context
from refunds_ai_api.services.ai_chat.workflows.classification import classify_workflow
from refunds_ai_api.services.ai_chat.workflows.context import resolve_workflow_context
from refunds_ai_api.services.ai_chat.workflows.objects import (
    ConversationObjectKind,
    resolve_conversation_object,
)

from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    FakeApplicationService,
    MusicCollectionApplicationService,
    NoToolModelClient,
    WindowsLicenseApplicationService,
    WorkflowRuntime,
)


class MechanicalKeyboardApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str):
        purchases = super().list_user_purchases(user_id)
        return [
            {
                **purchases[2],
                "product_name": "Mechanical Keyboard",
                "sku": "PHY-MECHANICAL-KEYBOARD",
            },
            *purchases[:2],
            purchases[3],
        ]


class CloudStorageApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str):
        purchases = super().list_user_purchases(user_id)
        purchases[0] = {
            **purchases[0],
            "product_name": "Cloud Storage Upgrade",
            "sku": "DIG-CLOUD-STORAGE",
        }
        return purchases


@pytest.mark.parametrize(
    ("message", "kind", "value"),
    [
        ("Can you please refund the Windows License?", "named_product", "Windows License"),
        ("Can you refund that item?", "contextual_reference", "that item"),
        ("Refund this order please", "contextual_reference", "this order"),
        (
            "Can I get a refund for my Music Collection?",
            "named_product",
            "Music Collection",
        ),
        ("Why can't you refund it?", "contextual_reference", "it"),
        ("Can you refund the subscription?", "purchase_type", "subscription"),
        ("Refund my refund", "none", None),
        (
            "I want to return the Mechanical Keyboard",
            "named_product",
            "Mechanical Keyboard",
        ),
    ],
)
def test_entity_extraction_regressions(
    message: str,
    kind: str,
    value: str | None,
) -> None:
    result = extract_entity(message)

    assert result.entity_kind == kind
    assert result.entity_value == value


def test_refund_action_phrase_is_rejected() -> None:
    result = extract_entity("Refund my refund")

    assert result.rejected_entity_candidates[0].as_dict() == {
        "text": "refund",
        "reason": "action_phrase",
    }


@pytest.mark.parametrize(
    "message",
    ["Can you refund that item?", "Refund this order please"],
)
def test_generic_references_never_run_product_search(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    def fail_product_search(*args, **kwargs):
        raise AssertionError("generic references must not run product search")

    monkeypatch.setattr(
        eligibility_resolver,
        "resolve_purchase_reference_for_state",
        fail_product_search,
    )
    monkeypatch.setattr(
        eligibility_resolver,
        "resolve_purchase_mention",
        fail_product_search,
    )
    monkeypatch.setattr(
        workflow_context,
        "match_purchase_reference_with_metadata",
        fail_product_search,
    )
    service = FakeApplicationService()

    conversation_state = {
            "active_purchase": {
                "purchase_id": PURCHASE_ID,
                "product_name": "Design Template Pack",
                "purchase_type": "digital",
            }
        }
    classification = classify_workflow(
        message,
        conversation_state=conversation_state,
        page_context={},
    )
    context = resolve_workflow_context(
        WorkflowRuntime(service),
        {
            "message": message,
            "conversation_state": conversation_state,
            "page_context": {},
            "customer_id": CUSTOMER_ID,
        },
        classification,
    )

    assert context.eligibility_resolution is not None
    assert context.eligibility_resolution.purchase_ids == [PURCHASE_ID]
    assert context.eligibility_resolution.context == "selected_purchase"


def test_page_contextual_reference_records_page_resolution_source() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    message = "Refund this order please"
    page_context = {"surface": "purchase_detail", "purchase_id": PURCHASE_ID}
    classification = classify_workflow(
        message,
        conversation_state={},
        page_context=page_context,
    )

    context = resolve_workflow_context(
        runtime,
        {
            "message": message,
            "customer_id": CUSTOMER_ID,
            "page_context": page_context,
            "conversation_state": {},
        },
        classification,
    )

    assert context.entity_extraction_result.as_dict() == {
        "intent": "refund_mutation",
        "raw_entity_text": "this order",
        "entity_kind": "contextual_reference",
        "entity_value": "this order",
        "rejected_entity_candidates": [],
        "context_resolution_source": "page_reference",
    }


def test_that_one_prefers_singular_active_result_set() -> None:
    conversation_object = resolve_conversation_object(
        "Can I refund that one?",
        conversation_state={
            "active_purchase": {
                "purchase_id": "active-purchase",
                "product_name": "Older Selection",
                "purchase_type": "digital",
            },
            "active_result_set": {
                "type": "purchase_history",
                "purchase_ids": [PURCHASE_ID],
                "label": "the matching purchase",
            },
        },
        page_context={},
    )

    assert conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET
    assert conversation_object.purchase_ids == (PURCHASE_ID,)


@pytest.mark.parametrize(
    ("application_service", "message", "product_name"),
    [
        (
            WindowsLicenseApplicationService(),
            "Can you please refund the Windows License?",
            "Windows License",
        ),
        (
            MusicCollectionApplicationService(),
            "Can I get a refund for my Music Collection?",
            "Music Collection",
        ),
        (
            MechanicalKeyboardApplicationService(),
            "I want to return the Mechanical Keyboard",
            "Mechanical Keyboard",
        ),
    ],
)
def test_named_entities_resolve_to_catalog_purchases(
    application_service,
    message: str,
    product_name: str,
) -> None:
    classification = classify_workflow(
        message,
        conversation_state={},
        page_context={},
    )
    context = resolve_workflow_context(
        WorkflowRuntime(application_service),
        {
            "message": message,
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
        },
        classification,
    )

    assert context.entity_extraction_result.entity_kind == "named_product"
    assert context.resolved_purchase["product_name"] == product_name


def test_refund_my_refund_requires_entity_clarification() -> None:
    application_service = FakeApplicationService()
    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient(""),
    ).create_response(
        message="Refund my refund",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == (
        "Please choose one purchase by product name or order number before I "
        "start or issue a refund."
    )
    assert application_service.refund_workflow_requests == []
    assert result.conversation_state["entity_extraction_result"]["entity_kind"] == "none"


@pytest.mark.parametrize(
    "message",
    [
        "Am I able to refund the Cloud Storage Upgrade?",
        "Am I able to refund the cloud storage upgrade?",
        "Am I able to refund teh cloud strage upgrade?",
    ],
)
def test_named_cloud_storage_eligibility_resolves_from_full_history(
    message: str,
) -> None:
    context = _resolve_cloud_storage_context(message, {})

    assert context.current_message_entity is not None
    assert context.current_message_entity.entity_kind == "named_product"
    assert context.current_message_entity.resolution_scope == "full_purchase_history"
    assert context.current_message_entity.matched_purchase_id == PURCHASE_ID
    assert context.current_message_entity.match_confidence is not None
    assert context.current_message_entity.match_confidence >= 0.78
    assert context.eligibility_resolution is not None
    assert context.eligibility_resolution.purchase_ids == [PURCHASE_ID]
    assert context.eligibility_resolution.resolved_purchase["product_name"] == (
        "Cloud Storage Upgrade"
    )


@pytest.mark.parametrize(
    ("label", "purchase_ids"),
    [
        (
            "your subscriptions",
            ["40000000-0000-4000-8000-000000000004"],
        ),
        (
            "your physical purchases",
            ["40000000-0000-4000-8000-000000000003"],
        ),
    ],
)
def test_named_product_overrides_stale_active_result_set(
    label: str,
    purchase_ids: list[str],
) -> None:
    context = _resolve_cloud_storage_context(
        "Am I able to refund the Cloud Storage Upgrade?",
        {
            "active_result_set": {
                "type": "purchase_history",
                "label": label,
                "purchase_ids": purchase_ids,
            }
        },
    )

    assert context.eligibility_resolution is not None
    assert context.eligibility_resolution.purchase_ids == [PURCHASE_ID]
    assert context.previous_context_scope == label
    assert context.resolution_scope_used == "full_purchase_history"
    assert context.selected_purchase_id == PURCHASE_ID
    assert "active_result_set_overridden" in context.resolution_reason
    assert context.match_candidates[0]["product_name"] == "Cloud Storage Upgrade"


def test_contextual_item_eligibility_uses_page_purchase() -> None:
    service = CloudStorageApplicationService()
    message = "Am I able to refund this item?"
    page_context = {"surface": "purchase_detail", "purchase_id": PURCHASE_ID}
    classification = classify_workflow(
        message,
        conversation_state={},
        page_context=page_context,
    )

    context = resolve_workflow_context(
        WorkflowRuntime(service),
        {
            "message": message,
            "customer_id": CUSTOMER_ID,
            "page_context": page_context,
            "conversation_state": {},
        },
        classification,
    )

    assert context.eligibility_resolution is not None
    assert context.eligibility_resolution.purchase_ids == [PURCHASE_ID]
    assert context.resolution_scope_used == "page_reference"
    assert context.match_candidates == ()


def test_contextual_that_one_eligibility_uses_active_result_set() -> None:
    context = _resolve_cloud_storage_context(
        "Am I able to refund that one?",
        {
            "active_result_set": {
                "type": "purchase_history",
                "label": "the matching purchase",
                "purchase_ids": [PURCHASE_ID],
            }
        },
    )

    assert context.eligibility_resolution is not None
    assert context.eligibility_resolution.purchase_ids == [PURCHASE_ID]
    assert context.resolution_scope_used == "active_result_set"
    assert context.match_candidates == ()
    assert context.resolution_reason == "contextual_reference_used_active_result_set"


def test_named_product_executes_eligibility_with_full_history_audit(
    caplog,
) -> None:
    service = CloudStorageApplicationService()
    conversation_state = {
        "active_result_set": {
            "type": "subscriptions",
            "label": "your subscriptions",
            "purchase_ids": ["40000000-0000-4000-8000-000000000004"],
        }
    }

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        AIChatService(
            application_service=service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Cloud Storage Upgrade is eligible."),
        ).create_response(
            message="Am I able to refund the Cloud Storage Upgrade?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=conversation_state,
        )

    assert service.refund_workflow_requests == [PURCHASE_ID]
    context_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.context_resolved"
    )
    event_data = context_event["data"]
    assert event_data["current_message_entity"]["entity_kind"] == "named_product"
    assert event_data["previous_context_scope"] == "your subscriptions"
    assert event_data["resolution_scope_used"] == "full_purchase_history"
    assert event_data["selected_purchase_id"] == PURCHASE_ID
    assert "active_result_set_overridden" in event_data["resolution_reason"]
    assert event_data["match_candidates"][0]["product_name"] == (
        "Cloud Storage Upgrade"
    )


def _resolve_cloud_storage_context(
    message: str,
    conversation_state: dict,
):
    service = CloudStorageApplicationService()
    classification = classify_workflow(
        message,
        conversation_state=conversation_state,
        page_context={},
    )
    return resolve_workflow_context(
        WorkflowRuntime(service),
        {
            "message": message,
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": conversation_state,
        },
        classification,
    )

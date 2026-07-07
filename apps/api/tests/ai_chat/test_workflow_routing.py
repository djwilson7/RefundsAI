from __future__ import annotations

from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowKind, classify_workflow
from refunds_ai_api.services.ai_chat.workflows.context import resolve_workflow_context
from refunds_ai_api.services.ai_chat.workflows.execution import (
    block_invalid_workflow_transition,
    execute_workflow,
)

from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    FakeApplicationService,
    WorkflowRuntime,
)


def test_workflow_classification_uses_deterministic_precedence() -> None:
    assert (
        classify_workflow(
            "Start the refund if this is eligible.",
            conversation_state={},
            page_context={},
        ).kind
        is WorkflowKind.REFUND_MUTATION
    )
    assert (
        classify_workflow(
            "Is this refundable and what is the refund policy?",
            conversation_state={"selected_purchase_id": PURCHASE_ID},
            page_context={},
        ).kind
        is WorkflowKind.REFUND_ELIGIBILITY
    )
    assert (
        classify_workflow(
            "What is the refund policy for subscriptions?",
            conversation_state={},
            page_context={},
        ).kind
        is WorkflowKind.REFUND_POLICY
    )
    assert (
        classify_workflow(
            "How many subscriptions have I paid for?",
            conversation_state={},
            page_context={},
        ).kind
        is WorkflowKind.ACCOUNT_FACT
    )
    follow_up = classify_workflow(
        "What was the last one?",
        conversation_state={
            "active_result_set": {
                "type": "subscriptions",
                "purchase_ids": ["purchase-1", "purchase-2"],
                "sort": "purchase_date_desc",
                "label": "your subscriptions",
            }
        },
        page_context={},
    )
    assert follow_up.kind is WorkflowKind.ACCOUNT_FACT
    assert follow_up.reason == "active_result_set_follow_up"
    assert (
        classify_workflow(
            "Who plays football tonight?",
            conversation_state={},
            page_context={},
        ).kind
        is WorkflowKind.OFF_DOMAIN
    )

def test_workflow_context_resolves_page_reference_and_policy_purchase() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    classification = classify_workflow(
        "What is the refund policy for this item?",
        conversation_state={},
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
    )

    context = resolve_workflow_context(
        runtime,
        {
            "message": "What is the refund policy for this item?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
            "conversation_state": {},
        },
        classification,
    )

    assert context.kind is WorkflowKind.REFUND_POLICY
    assert context.page_reference["purchase"]["id"] == PURCHASE_ID
    assert context.policy_lookup_query == {
        "scope": "product_type",
        "purchase_type": "digital",
    }
    assert context.resolved_purchase["product_name"] == "Design Template Pack"

def test_workflow_context_blocks_unresolved_product_reference() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    classification = classify_workflow(
        "Can I refund the Developer Toolkit?",
        conversation_state={},
        page_context={},
    )

    context = resolve_workflow_context(
        runtime,
        {
            "message": "Can I refund the Developer Toolkit?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
        },
        classification,
    )

    assert context.kind is WorkflowKind.REFUND_ELIGIBILITY
    assert context.unresolved_product_reference == "Developer Toolkit"

def test_workflow_context_resolves_latest_follow_up_from_active_result_set() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    conversation_state = {
        "selected_purchase_type": "digital",
        "selected_purchase_ids": [
            PURCHASE_ID,
            "40000000-0000-4000-8000-000000000002",
        ],
        "selected_scope_label": "your digital purchases",
    }
    classification = classify_workflow(
        "What was the last one?",
        conversation_state=conversation_state,
        page_context={},
    )

    context = resolve_workflow_context(
        runtime,
        {
            "message": "What was the last one?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": conversation_state,
        },
        classification,
    )

    assert context.kind is WorkflowKind.ACCOUNT_FACT
    assert context.resolved_context_purchase["id"] == (
        "40000000-0000-4000-8000-000000000002"
    )
    assert context.resolved_context_purchase["product_name"] == "Icon Set"

def test_workflow_context_resolves_eligibility_and_policy_from_active_purchase() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    conversation_state = {
        "selected_purchase_id": "40000000-0000-4000-8000-000000000003",
        "selected_product": "Keyboard",
        "selected_purchase_type": "physical",
    }

    eligibility_classification = classify_workflow(
        "Is it eligible?",
        conversation_state=conversation_state,
        page_context={},
    )
    eligibility_context = resolve_workflow_context(
        runtime,
        {
            "message": "Is it eligible?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": conversation_state,
        },
        eligibility_classification,
    )

    assert eligibility_context.kind is WorkflowKind.REFUND_ELIGIBILITY
    assert eligibility_context.eligibility_resolution.purchase_ids == [
        "40000000-0000-4000-8000-000000000003"
    ]
    assert eligibility_context.eligibility_resolution.context == "selected_purchase"

    policy_classification = classify_workflow(
        "What is the refund policy for it?",
        conversation_state=conversation_state,
        page_context={},
    )
    policy_context = resolve_workflow_context(
        runtime,
        {
            "message": "What is the refund policy for it?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": conversation_state,
        },
        policy_classification,
    )

    assert policy_context.kind is WorkflowKind.REFUND_POLICY
    assert policy_context.policy_lookup_query == {
        "scope": "product_type",
        "purchase_type": "physical",
    }
    assert policy_context.resolved_purchase["product_name"] == "Keyboard"

def test_workflow_execution_runs_deterministic_tools_by_workflow() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())

    threshold_context = resolve_workflow_context(
        runtime,
        {
            "message": "How many purchases have I made over $100?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
            "tool_calls": [],
        },
        classify_workflow(
            "How many purchases have I made over $100?",
            conversation_state={},
            page_context={},
        ),
    )
    _state, threshold_results = execute_workflow(
        runtime,
        {
            "message": "How many purchases have I made over $100?",
            "customer_id": CUSTOMER_ID,
            "tool_calls": [],
        },
        threshold_context,
    )
    assert threshold_results[0]["name"] == "get_purchase_count_by_amount_threshold"

    date_context = resolve_workflow_context(
        runtime,
        {
            "message": "Show me purchases from last week.",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
            "tool_calls": [],
        },
        classify_workflow(
            "Show me purchases from last week.",
            conversation_state={},
            page_context={},
        ),
    )
    _state, date_results = execute_workflow(
        runtime,
        {
            "message": "Show me purchases from last week.",
            "customer_id": CUSTOMER_ID,
            "tool_calls": [],
        },
        date_context,
    )
    assert date_results[0]["name"] == "get_purchase_history_by_date_range"

    history_context = resolve_workflow_context(
        runtime,
        {
            "message": "Summarize my purchases.",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
            "tool_calls": [],
        },
        classify_workflow(
            "Summarize my purchases.",
            conversation_state={},
            page_context={},
        ),
    )
    _state, history_results = execute_workflow(
        runtime,
        {
            "message": "Summarize my purchases.",
            "customer_id": CUSTOMER_ID,
            "tool_calls": [],
        },
        history_context,
    )
    assert history_results[0]["name"] == "get_customer_purchase_history"

def test_workflow_execution_runs_policy_and_eligibility_tools() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())

    policy_context = resolve_workflow_context(
        runtime,
        {
            "message": "What is the refund policy for digital products?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
            "tool_calls": [],
        },
        classify_workflow(
            "What is the refund policy for digital products?",
            conversation_state={},
            page_context={},
        ),
    )
    _state, policy_results = execute_workflow(
        runtime,
        {
            "message": "What is the refund policy for digital products?",
            "customer_id": CUSTOMER_ID,
            "tool_calls": [],
        },
        policy_context,
    )
    assert policy_results[0]["name"] == "get_refund_policy"
    assert policy_results[0]["result"]["purchase_type"] == "digital"

    eligibility_context = resolve_workflow_context(
        runtime,
        {
            "message": "Can I refund this item?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
            "conversation_state": {},
            "tool_calls": [],
        },
        classify_workflow(
            "Can I refund this item?",
            conversation_state={},
            page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        ),
    )
    _state, eligibility_results = execute_workflow(
        runtime,
        {
            "message": "Can I refund this item?",
            "customer_id": CUSTOMER_ID,
            "tool_calls": [],
        },
        eligibility_context,
    )
    assert eligibility_results[0]["name"] == "get_refund_eligibility"
    assert eligibility_results[0]["result"]["resolved_purchase_ids"] == [PURCHASE_ID]

def test_workflow_execution_blocks_mutation_and_skips_off_domain_tools() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    mutation_classification = classify_workflow(
        "Issue the refund.",
        conversation_state={},
        page_context={},
    )
    mutation_context = resolve_workflow_context(
        runtime,
        {
            "message": "Issue the refund.",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
        },
        mutation_classification,
    )

    blocked_state = block_invalid_workflow_transition(
        runtime,
        {
            "message": "Issue the refund.",
            "customer_id": CUSTOMER_ID,
            "conversation_state": {},
        },
        mutation_context,
    )

    assert blocked_state["assistant_response"] == (
        "Please choose one purchase by product name or order number before I "
        "start or issue a refund."
    )

    off_domain_context = resolve_workflow_context(
        runtime,
        {
            "message": "Who plays football tonight?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {},
            "tool_calls": [],
        },
        classify_workflow(
            "Who plays football tonight?",
            conversation_state={},
            page_context={},
        ),
    )
    _state, off_domain_results = execute_workflow(
        runtime,
        {
            "message": "Who plays football tonight?",
            "customer_id": CUSTOMER_ID,
            "tool_calls": [],
        },
        off_domain_context,
    )
    assert off_domain_results == []

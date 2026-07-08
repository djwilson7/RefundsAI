from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from refunds_ai_api.main import create_app
from refunds_ai_api.routes.chat import get_ai_chat_service
from refunds_ai_api.services.ai_chat import (
    EMPTY_CONVERSATION_STATE,
    AIChatResult,
    AIChatService,
    ModelToolCall,
    ModelTurn,
)
from refunds_ai_api.services.refund_policy import RefundWorkflowError

CUSTOMER_ID = "20000000-0000-4000-8000-000000000001"
PURCHASE_ID = "40000000-0000-4000-8000-000000000001"


def _maybe_inject_dummy_call(calls: list, messages: list[dict[str, Any]], tools: Any) -> None:
    if not tools and not calls:
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        from refunds_ai_api.services.ai_chat.prompts import SYSTEM_PROMPT
        from refunds_ai_api.services.ai_chat.nodes.tool_selection import (
            validate_customer_account_tool_schema,
            get_customer_purchase_history_tool_schema,
            get_purchase_count_by_amount_threshold_tool_schema,
            get_purchase_history_by_date_range_tool_schema,
            get_refund_policy_tool_schema,
            get_refund_eligibility_tool_schema,
        )
        dummy_tools = [
            validate_customer_account_tool_schema(),
            get_customer_purchase_history_tool_schema(),
            get_purchase_count_by_amount_threshold_tool_schema(),
            get_purchase_history_by_date_range_tool_schema(),
            get_refund_policy_tool_schema(),
            get_refund_eligibility_tool_schema(),
        ]
        calls.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "tools": dummy_tools
        })


class FakeModelClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        if self.fail:
            raise RuntimeError("model offline")

        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-1",
                        name="get_customer_purchase_history",
                        arguments={"customer_id": "not-the-active-customer"},
                    )
                ],
            )

        return ModelTurn(
            content="You made 2 digital purchases totaling $75.00.",
            tool_calls=[],
        )

class FakeApplicationService:
    def __init__(self) -> None:
        self.purchase_requests: list[str] = []
        self.refund_workflow_called = False
        self.refund_workflow_requests: list[str] = []
        self.refund_confirmations: dict[str, dict[str, Any]] = {}

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        self.purchase_requests.append(user_id)
        return [
            {
                "id": PURCHASE_ID,
                "order_number": "RAI-10001",
                "purchase_type": "digital",
                "product_name": "Design Template Pack",
                "sku": "DIG-TEMPLATE-001",
                "amount_cents": 4500,
                "purchased_at": datetime(2026, 6, 20, 14, 30, tzinfo=UTC),
                "status": "completed",
                "details_url": f"/api/purchases/{PURCHASE_ID}/details",
            },
            {
                "id": "40000000-0000-4000-8000-000000000002",
                "order_number": "RAI-10002",
                "purchase_type": "digital",
                "product_name": "Icon Set",
                "sku": "DIG-ICONS-001",
                "amount_cents": 3000,
                "purchased_at": datetime(2026, 6, 21, 14, 30, tzinfo=UTC),
                "status": "redeemed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000002/details",
            },
            {
                "id": "40000000-0000-4000-8000-000000000003",
                "order_number": "RAI-10003",
                "purchase_type": "physical",
                "product_name": "Keyboard",
                "sku": "PHY-KEYBOARD-001",
                "amount_cents": 12500,
                "purchased_at": datetime(2026, 6, 22, 14, 30, tzinfo=UTC),
                "status": "completed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000003/details",
            },
            {
                "id": "40000000-0000-4000-8000-000000000004",
                "order_number": "RAI-10004",
                "purchase_type": "subscription",
                "product_name": "Pro Subscription",
                "sku": "SUB-PRO-001",
                "amount_cents": 999,
                "purchased_at": datetime(2026, 6, 23, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000004/details",
            },
        ]

    def get_user(self, user_id: str) -> dict[str, Any]:
        return {
            "id": user_id,
            "first_name": "Avery",
            "last_name": "Customer",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "display_name": "Avery Customer",
            "roles": [{"key": "customer", "name": "Customer"}],
        }

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        self.refund_workflow_called = True
        self.refund_workflow_requests.append(purchase_id)
        workflows = {
            PURCHASE_ID: {
                "purchase_id": PURCHASE_ID,
                "purchase_type": "digital",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "invalidate_digital_entitlement",
                "refundable_amount_cents": 4500,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "completed",
                    "code_redeemed": False,
                },
            },
            "40000000-0000-4000-8000-000000000002": {
                "purchase_id": "40000000-0000-4000-8000-000000000002",
                "purchase_type": "digital",
                "can_enter_refund_workflow": False,
                "can_prepare_refund": False,
                "can_issue_funds": False,
                "refund_stage": "blocked",
                "required_action": "none",
                "refundable_amount_cents": 0,
                "refund_outcome": "none",
                "reasons": ["digital_entitlement_redeemed"],
                "policy_facts": {
                    "purchase_status": "redeemed",
                    "code_redeemed": True,
                },
            },
            "40000000-0000-4000-8000-000000000003": {
                "purchase_id": "40000000-0000-4000-8000-000000000003",
                "purchase_type": "physical",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "generate_return_label",
                "refundable_amount_cents": 12500,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "completed",
                    "carrier_accepted_at": None,
                },
            },
            "40000000-0000-4000-8000-000000000004": {
                "purchase_id": "40000000-0000-4000-8000-000000000004",
                "purchase_type": "subscription",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "cancel_subscription",
                "refundable_amount_cents": 999,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "subscribed",
                    "subscription_active": True,
                },
            },
            "40000000-0000-4000-8000-000000000005": {
                "purchase_id": "40000000-0000-4000-8000-000000000005",
                "purchase_type": "subscription",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "cancel_subscription",
                "refundable_amount_cents": 3999,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "subscribed",
                    "subscription_active": True,
                },
            },
        }
        return workflows[purchase_id]

    def record_refund_confirmation(
        self,
        *,
        customer_id: str,
        purchase_id: str,
        purchase_type: str,
        received_message: str,
        expected_command: str,
        granted_at: datetime,
        matched: bool,
        source: str,
    ) -> dict[str, Any]:
        owned_purchase = next(
            (
                purchase
                for purchase in self.list_user_purchases(customer_id)
                if str(purchase["id"]) == purchase_id
                and purchase["purchase_type"] == purchase_type
            ),
            None,
        )
        if owned_purchase is None:
            raise RefundWorkflowError("Refund confirmation purchase ownership mismatch.")

        self.refund_confirmations[purchase_id] = {
            "refund_confirmation_granted": True,
            "refund_confirmation_message": received_message,
            "refund_confirmation_granted_at": granted_at,
            "refund_confirmation_expected_command": expected_command,
            "refund_confirmation_matched": matched,
            "refund_confirmation_source": source,
            "refund_confirmation_customer_id": customer_id,
            "refund_confirmation_purchase_id": purchase_id,
            "refund_confirmation_consumed_at": None,
            "refund_confirmation_consumed_by_action": None,
        }
        return self.get_refund_confirmation(purchase_id, purchase_type)

    def get_refund_confirmation(
        self,
        purchase_id: str,
        purchase_type: str,
    ) -> dict[str, Any]:
        confirmation = self.refund_confirmations.get(purchase_id)
        if confirmation is None:
            return {
                "refund_confirmation_granted": False,
                "refund_confirmation_message": None,
                "refund_confirmation_granted_at": None,
                "refund_confirmation_expected_command": None,
                "refund_confirmation_matched": False,
                "refund_confirmation_source": None,
                "refund_confirmation_customer_id": None,
                "refund_confirmation_purchase_id": purchase_id,
                "refund_confirmation_consumed_at": None,
                "refund_confirmation_consumed_by_action": None,
            }
        return dict(confirmation)

    def consume_refund_confirmation(
        self,
        *,
        customer_id: str,
        purchase_id: str,
        purchase_type: str,
        expected_command: str,
        consumed_at: datetime,
        consumed_by_action: str,
    ) -> dict[str, Any]:
        confirmation = self.refund_confirmations.get(purchase_id)
        if (
            confirmation is None
            or confirmation.get("refund_confirmation_granted") is not True
            or confirmation.get("refund_confirmation_matched") is not True
            or confirmation.get("refund_confirmation_customer_id") != customer_id
            or confirmation.get("refund_confirmation_purchase_id") != purchase_id
            or confirmation.get("refund_confirmation_expected_command")
            != expected_command
            or confirmation.get("refund_confirmation_consumed_at") is not None
            or confirmation.get("refund_confirmation_consumed_by_action") is not None
        ):
            raise RefundWorkflowError("Refund confirmation is not valid for this refund action.")

        confirmation.update(
            {
                "refund_confirmation_consumed_at": consumed_at,
                "refund_confirmation_consumed_by_action": consumed_by_action,
            }
        )
        return self.get_refund_confirmation(purchase_id, purchase_type)

    def request_refund(self, purchase_id: str) -> dict[str, Any]:
        raise AssertionError("Refund mutations must not be called by chat graph.")

    def issue_refund(self, purchase_id: str) -> dict[str, Any]:
        raise AssertionError("Refund mutations must not be called by chat graph.")

class MutableRefundApplicationService(FakeApplicationService):
    def __init__(self) -> None:
        super().__init__()
        self.request_refund_requests: list[str] = []
        self.issue_refund_requests: list[str] = []
        self.prepared_purchase_ids: set[str] = set()
        self.issued_purchase_ids: set[str] = set()

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        workflow = dict(super().get_refund_workflow(purchase_id))
        if purchase_id in self.issued_purchase_ids:
            workflow.update(
                {
                    "can_enter_refund_workflow": False,
                    "can_prepare_refund": False,
                    "can_issue_funds": False,
                    "refund_stage": "issued",
                    "required_action": "none",
                }
            )
            return workflow
        if purchase_id in self.prepared_purchase_ids:
            workflow.update(
                {
                    "can_enter_refund_workflow": True,
                    "can_prepare_refund": False,
                    "can_issue_funds": True,
                    "refund_stage": "prepared",
                    "required_action": "issue_funds",
                }
            )
        return workflow

    def request_refund(self, purchase_id: str) -> dict[str, Any]:
        self.request_refund_requests.append(purchase_id)
        self.prepared_purchase_ids.add(purchase_id)
        return self.get_refund_workflow(purchase_id)

    def issue_refund(self, purchase_id: str) -> dict[str, Any]:
        self.issue_refund_requests.append(purchase_id)
        self.issued_purchase_ids.add(purchase_id)
        return self.get_refund_workflow(purchase_id)

class FailedPersistenceRefundApplicationService(MutableRefundApplicationService):
    def request_refund(self, purchase_id: str) -> dict[str, Any]:
        self.request_refund_requests.append(purchase_id)
        workflow = dict(FakeApplicationService.get_refund_workflow(self, purchase_id))
        workflow.update(
            {
                "can_prepare_refund": False,
                "can_issue_funds": True,
                "refund_stage": "prepared",
                "required_action": "issue_funds",
            }
        )
        return workflow

class DeveloperToolkitApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": "40000000-0000-4000-8000-000000000005",
                "order_number": "RAI-10005",
                "purchase_type": "subscription",
                "product_name": "Developer Toolkit",
                "sku": "SUB-DEVELOPER-TOOLKIT",
                "amount_cents": 3999,
                "purchased_at": datetime(2026, 6, 24, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000005/details",
            },
            *purchases,
        ]

class AmbiguousProductApplicationService(DeveloperToolkitApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": "40000000-0000-4000-8000-000000000006",
                "order_number": "RAI-10006",
                "purchase_type": "subscription",
                "product_name": "Developer Toolkit Plus",
                "sku": "SUB-DEVELOPER-TOOLKIT-PLUS",
                "amount_cents": 5999,
                "purchased_at": datetime(2026, 6, 25, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000006/details",
            },
            *purchases,
        ]

class LastWeekApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                **purchases[0],
                "purchased_at": datetime(2026, 7, 1, 14, 30, tzinfo=UTC),
            },
            {
                **purchases[2],
                "purchased_at": datetime(2026, 7, 3, 14, 30, tzinfo=UTC),
            },
            {
                **purchases[3],
                "purchased_at": datetime(2026, 6, 20, 14, 30, tzinfo=UTC),
            },
        ]

class WindowsLicenseApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": "40000000-0000-4000-8000-000000000007",
                "order_number": "RAI-10007",
                "purchase_type": "digital",
                "product_name": "Windows License",
                "sku": "DIG-WINDOWS-LICENSE",
                "amount_cents": 14900,
                "purchased_at": datetime(2026, 6, 26, 14, 30, tzinfo=UTC),
                "status": "completed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000007/details",
            },
            *purchases,
        ]

class MusicCollectionApplicationService(DeveloperToolkitApplicationService):
    music_collection_id = "40000000-0000-4000-8000-000000000008"

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": self.music_collection_id,
                "order_number": "RAI-10008",
                "purchase_type": "digital",
                "product_name": "Music Collection",
                "sku": "DIG-MUSIC-COLLECTION",
                "amount_cents": 2499,
                "purchased_at": datetime(2026, 6, 27, 14, 30, tzinfo=UTC),
                "status": "completed",
                "details_url": f"/api/purchases/{self.music_collection_id}/details",
            },
            *purchases,
        ]

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        if purchase_id == self.music_collection_id:
            self.refund_workflow_called = True
            self.refund_workflow_requests.append(purchase_id)
            return {
                "purchase_id": self.music_collection_id,
                "purchase_type": "digital",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "invalidate_digital_entitlement",
                "refundable_amount_cents": 2499,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "completed",
                    "code_redeemed": False,
                },
            }
        return super().get_refund_workflow(purchase_id)

class UnknownToolModelClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls += 1
        if tools:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-unknown",
                        name="unsupported_tool",
                        arguments={},
                    )
                ],
            )
        return ModelTurn(content="You made 4 purchases.", tool_calls=[])

class NoToolModelClient:
    def __init__(self, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        self.calls.append({"messages": messages, "tools": tools})
        if not tools:
            return ModelTurn(content=self.response, tool_calls=[])
        return ModelTurn(content=None, tool_calls=[])

class BroadHistoryForDateRangeModelClient:
    def __init__(self, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        self.calls.append({"messages": messages, "tools": tools})
        if tools:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-broad-history",
                        name="get_customer_purchase_history",
                        arguments={},
                    )
                ],
            )
        return ModelTurn(content=self.response, tool_calls=[])

class ToolCallingModelClient:
    def __init__(self, tool_call: ModelToolCall, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.tool_call = tool_call
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        self.calls.append({"messages": messages, "tools": tools})
        if tools:
            return ModelTurn(content=None, tool_calls=[self.tool_call])
        return ModelTurn(content=self.response, tool_calls=[])

class ActiveResultSetAnswerModelClient:
    def __init__(self, *, mode: str = "list") -> None:
        self.calls: list[dict[str, Any]] = []
        self.mode = mode
        self.final_response_context: dict[str, Any] | None = None

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        self.calls.append({"messages": messages, "tools": tools})
        if tools:
            return ModelTurn(content=None, tool_calls=[])

        compact_message = next(
            message
            for message in messages
            if message["content"].startswith("Compact conversation context")
        )
        payload = json.loads(compact_message["content"].split(": ", 1)[1])
        response_context = payload["response_context"]
        self.final_response_context = response_context
        items = response_context["active_result_set"]["items"]
        if self.mode == "first":
            item = items[0]
            return ModelTurn(content=f"The first one was {item['product_name']}.", tool_calls=[])
        product_names = ", ".join(item["product_name"] for item in items)
        return ModelTurn(
            content=f"{response_context['answer_scope']}: {product_names}.",
            tool_calls=[],
        )

class LeakyFinalResponseModelClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        self.calls.append({"messages": messages, "tools": tools})
        if tools:
            return ModelTurn(content=None, tool_calls=[])
        return ModelTurn(
            content=(
                "The workflow mutation used issue_funds after the backend "
                "verified the persisted state."
            ),
            tool_calls=[],
        )

class MalformedPseudoToolModelClient:
    def __init__(self, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        _maybe_inject_dummy_call(self.calls, messages, tools)
        self.calls.append({"messages": messages, "tools": tools})
        if tools:
            return ModelTurn(
                content='to=get_customer_purchase_history  {}',
                tool_calls=[],
            )
        return ModelTurn(content=self.response, tool_calls=[])

class GuardedNoToolChatService(AIChatService):
    def _execute_tools(self, state):  # type: ignore[no-untyped-def]
        return {**state, "tool_results": [], "account_fact_intent": True}

class FinalFailureModelClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        if not tools and self.calls == 0:
            self.calls += 1
        self.calls += 1
        if tools:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-1",
                        name="get_customer_purchase_history",
                        arguments={"customer_id": "not-the-active-customer"},
                    )
                ],
            )
        raise RuntimeError("final model offline")

class FailingPurchaseApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        raise RuntimeError("database offline")

class StaticChatService:
    audit_writer = None

    def create_response(
        self,
        *,
        message: str,
        customer_id: str | None,
        purchase_id: str | None,
        page_context: dict[str, Any] | None = None,
        conversation_state: dict[str, Any] | None = None,
        trace_step_start: int = 1,
        audit_session: Any = None,
    ) -> AIChatResult:
        return AIChatResult(
            content=f"Received {message}",
            graph_ready=True,
            conversation_state=conversation_state or dict(EMPTY_CONVERSATION_STATE),
            next_trace_step=trace_step_start,
        )

def build_client(chat_service: Any) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_ai_chat_service] = lambda: chat_service
    return TestClient(app)

class WorkflowRuntime:
    def __init__(self, application_service: Any) -> None:
        self.application_service = application_service
        self.model = "gpt-5.4-mini"

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from refunds_ai_api.main import create_app
from refunds_ai_api.repositories.application import (
    ApplicationRepository,
    EntityNotFoundError,
    PurchaseDetailsNotFoundError,
    RepositoryConflictError,
    group_user_role_rows,
)
from refunds_ai_api.routes.application import get_application_service
from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.refund_policy import RefundWorkflowError

USER_ID = "10000000-0000-4000-8000-000000000001"
PURCHASE_ID = "40000000-0000-4000-8000-000000000001"
USER_CREATED_AT = datetime(2026, 7, 3, 0, 0, tzinfo=UTC)


class StubApplicationService:
    def __init__(
        self,
        users: list[dict[str, Any]] | None = None,
        user: dict[str, Any] | None = None,
        purchases: list[dict[str, Any]] | None = None,
        purchase_detail: dict[str, Any] | None = None,
        refund_eligibility: dict[str, Any] | None = None,
        refund_workflow: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.users = users or []
        self.user = user
        self.purchases = purchases or []
        self.purchase_detail = purchase_detail
        self.refund_eligibility = refund_eligibility
        self.refund_workflow = refund_workflow or refund_eligibility
        self.error = error

    def list_mock_users(self) -> list[dict[str, Any]]:
        if self.error:
            raise self.error
        return self.users

    def get_user(self, user_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        if self.user is None:
            raise AssertionError("Stub user was not configured.")
        return self.user

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        if self.error:
            raise self.error
        return self.purchases

    def get_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        if self.purchase_detail is None:
            raise AssertionError("Stub purchase detail was not configured.")
        return self.purchase_detail

    def get_refund_eligibility(self, purchase_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        if self.refund_eligibility is None:
            raise AssertionError("Stub refund eligibility was not configured.")
        return self.refund_eligibility

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        if self.refund_workflow is None:
            raise AssertionError("Stub refund workflow was not configured.")
        return self.refund_workflow

    def request_refund(self, purchase_id: str) -> dict[str, Any]:
        return self.get_refund_workflow(purchase_id)

    def issue_refund(self, purchase_id: str) -> dict[str, Any]:
        return self.get_refund_workflow(purchase_id)

    def redeem_digital_code(self, purchase_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        if self.purchase_detail is None:
            raise AssertionError("Stub purchase detail was not configured.")
        return self.purchase_detail

    def confirm_carrier_acceptance(self, purchase_id: str) -> dict[str, Any]:
        return self.get_refund_workflow(purchase_id)

    def get_purchase_for_refund_policy(self, purchase_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        return {
            "purchase": {
                "id": PURCHASE_ID,
                "purchase_type": "digital",
                "amount_cents": 4500,
                "purchased_at": datetime(2026, 6, 20, 14, 30, tzinfo=UTC),
                "status": "completed",
                "refund_requested_at": None,
                "refunded_at": None,
                "refund_amount_cents": None,
                "refund_outcome": None,
            },
            "detail": {
                "code_redeemed": False,
                "code_redeemed_at": None,
                "code_invalidated_at": None,
                "refund_lock_reason": None,
                "refund_window_expires_at": datetime(2026, 7, 5, 14, 30, tzinfo=UTC),
            },
        }


class StubCursor:
    def __init__(self, connection: "StubConnection") -> None:
        self.connection = connection
        self.result: list[dict[str, Any]] = []
        self.rowcount = -1

    def __enter__(self) -> "StubCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str, params=None) -> None:
        self.connection.executed.append((statement, params))
        normalized = " ".join(statement.split()).lower()
        self.rowcount = 1
        if "from public.purchases" in normalized:
            self.result = [self.connection.purchase_row]
        elif "from public.digital_purchase_details" in normalized:
            self.result = [self.connection.detail_rows["digital"]]
        elif "from public.physical_purchase_details" in normalized:
            self.result = [self.connection.detail_rows["physical"]]
        elif "from public.subscription_purchase_details" in normalized:
            self.result = [self.connection.detail_rows["subscription"]]
        else:
            self.result = []
        if normalized.startswith("update") and self.connection.force_conflict:
            self.rowcount = 0

    def fetchone(self) -> dict[str, Any] | None:
        return self.result[0] if self.result else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self.result


class StubConnection:
    def __init__(self, purchase_type: str) -> None:
        self.executed: list[tuple[str, tuple[str, ...] | None]] = []
        self.purchase_row = {
            "id": PURCHASE_ID,
            "purchase_type": purchase_type,
            "amount_cents": 12000,
            "purchased_at": datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
            "status": "completed",
            "refund_requested_at": None,
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        self.force_conflict = False
        self.detail_rows = {
            "digital": {
                "issued_code": "DIG-RAI-10001",
                "code_redeemed": False,
                "code_redeemed_at": None,
                "code_invalidated_at": None,
                "code_delivered_at": datetime(2026, 6, 1, 14, 5, tzinfo=UTC),
                "refund_window_expires_at": datetime(2026, 6, 16, 14, 0, tzinfo=UTC),
                "refund_lock_reason": None,
            },
            "physical": {
                "scheduled_delivery_at": datetime(2026, 6, 3, 14, 0, tzinfo=UTC),
                "delivered_at": None,
                "return_status": "not_requested",
                "carrier": "UPS",
                "tracking_number": "TRK-RAI-10001",
                "return_barcode_generated": False,
                "return_label_created_at": None,
                "accepted_by_carrier_at": None,
                "return_requested_at": None,
                "return_authorized_at": None,
                "return_received_at": None,
                "return_rejected_at": None,
                "return_rejection_reason": None,
                "refund_window_expires_at": datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
            },
            "subscription": {
                "period_start": datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
                "period_end": datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
                "cancelled_at": None,
                "service_ended_at": None,
                "auto_renew": True,
                "refund_proration_mode": "none",
                "full_refund_window_expires_at": datetime(2026, 6, 3, 14, 0, tzinfo=UTC),
                "refund_window_expires_at": datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
            },
        }

    def cursor(self) -> StubCursor:
        return StubCursor(self)

    def transaction(self) -> "StubTransaction":
        return StubTransaction()


class StubConnectionProvider:
    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection

    @contextmanager
    def open(self):
        yield self.connection


class StubTransaction:
    def __enter__(self) -> "StubTransaction":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def build_user() -> dict[str, Any]:
    return {
        "id": USER_ID,
        "first_name": "John",
        "last_name": "Smith",
        "created_at": USER_CREATED_AT,
        "display_name": "John Smith",
        "roles": [{"key": "customer", "name": "Customer"}],
    }


def build_user_json() -> dict[str, Any]:
    return {**build_user(), "created_at": "2026-07-03T00:00:00Z"}


def build_purchase() -> dict[str, Any]:
    return {
        "id": PURCHASE_ID,
        "order_number": "RAI-10001",
        "purchase_type": "physical",
        "product_name": "Wireless Headphones",
        "sku": "PHY-HEADPHONES-001",
        "amount_cents": 12999,
        "purchased_at": datetime(2026, 6, 20, 14, 30, tzinfo=UTC),
        "status": "completed",
        "details_url": f"/api/purchases/{PURCHASE_ID}/details",
    }


def build_client(service: StubApplicationService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_application_service] = lambda: service
    return TestClient(app)


def test_list_mock_users_endpoint_returns_selectable_users() -> None:
    client = build_client(StubApplicationService(users=[build_user()]))

    response = client.get("/api/users/mock")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["users"] == [build_user_json()]
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_get_user_endpoint_returns_role_info() -> None:
    client = build_client(StubApplicationService(user=build_user()))

    response = client.get(f"/api/users/{USER_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user"] == build_user_json()


def test_list_user_purchases_endpoint_returns_frontend_ready_rows() -> None:
    purchase = build_purchase()
    client = build_client(StubApplicationService(purchases=[purchase]))

    response = client.get(f"/api/users/{USER_ID}/purchases")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["purchases"] == [
        {
            **purchase,
            "purchased_at": "2026-06-20T14:30:00Z",
        }
    ]


def test_get_purchase_details_endpoint_returns_backend_resolved_detail_payload() -> None:
    client = build_client(
        StubApplicationService(
            purchase_detail={
                "purchase_id": PURCHASE_ID,
                "purchase_type": "physical",
                "details": {
                    "scheduled_delivery_at": datetime(2026, 6, 3, 14, tzinfo=UTC),
                    "delivered_at": None,
                    "return_status": "not_requested",
                    "carrier": "UPS",
                    "tracking_number": "TRK-RAI-10001",
                    "accepted_by_carrier_at": None,
                },
            }
        )
    )

    response = client.get(f"/api/purchases/{PURCHASE_ID}/details")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "purchase_id": PURCHASE_ID,
        "purchase_type": "physical",
        "details": {
            "scheduled_delivery_at": "2026-06-03T14:00:00Z",
            "delivered_at": None,
            "return_status": "not_requested",
            "carrier": "UPS",
            "tracking_number": "TRK-RAI-10001",
            "accepted_by_carrier_at": None,
        },
    }


def test_get_purchase_details_endpoint_reports_missing_purchase() -> None:
    client = build_client(
        StubApplicationService(error=EntityNotFoundError("Purchase was not found."))
    )

    response = client.get(f"/api/purchases/{PURCHASE_ID}/details")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == {
        "code": "PURCHASE_NOT_FOUND",
        "message": "Purchase was not found.",
    }


def test_get_purchase_details_endpoint_reports_missing_detail_row() -> None:
    client = build_client(
        StubApplicationService(
            error=PurchaseDetailsNotFoundError("Purchase detail row was not found.")
        )
    )

    response = client.get(f"/api/purchases/{PURCHASE_ID}/details")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == {
        "code": "PURCHASE_DETAILS_NOT_FOUND",
        "message": "Purchase detail row was not found.",
    }


def test_get_refund_eligibility_endpoint_returns_policy_result() -> None:
    client = build_client(
        StubApplicationService(
            refund_eligibility={
                "purchase_id": PURCHASE_ID,
                "purchase_type": "digital",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": False,
                "can_issue_funds": True,
                "refund_stage": "prepared",
                "required_action": "issue_funds",
                "refundable_amount_cents": 4500,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "completed",
                    "refund_window_expires_at": datetime(2026, 7, 5, 14, 30, tzinfo=UTC),
                    "evaluated_at": datetime(2026, 7, 3, 14, 30, tzinfo=UTC),
                    "code_redeemed": False,
                    "code_invalidated_at": None,
                    "refund_lock_reason": None,
                },
            }
        )
    )

    response = client.get(f"/api/purchases/{PURCHASE_ID}/refund/eligibility")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "purchase_id": PURCHASE_ID,
        "purchase_type": "digital",
        "can_enter_refund_workflow": True,
        "can_prepare_refund": False,
        "can_issue_funds": True,
        "refund_stage": "prepared",
        "required_action": "issue_funds",
        "refundable_amount_cents": 4500,
        "refund_outcome": "full",
        "reasons": [],
        "policy_facts": {
            "purchase_status": "completed",
            "refund_window_expires_at": "2026-07-05T14:30:00Z",
            "evaluated_at": "2026-07-03T14:30:00Z",
            "code_redeemed": False,
            "code_invalidated_at": None,
            "refund_lock_reason": None,
        },
    }


def test_request_refund_endpoint_returns_prepared_workflow() -> None:
    workflow = build_workflow()
    client = build_client(StubApplicationService(refund_workflow=workflow))

    response = client.post(f"/api/purchases/{PURCHASE_ID}/refund/request")

    assert response.status_code == 200
    assert response.json()["data"] == workflow


def test_request_refund_endpoint_reports_workflow_denial() -> None:
    client = build_client(
        StubApplicationService(error=RefundWorkflowError("Refund preparation is not allowed."))
    )

    response = client.post(f"/api/purchases/{PURCHASE_ID}/refund/request")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "REFUND_PREPARATION_NOT_ALLOWED",
        "message": "Refund preparation is not allowed.",
    }


def test_issue_refund_endpoint_returns_issued_workflow() -> None:
    workflow = {
        **build_workflow(),
        "can_enter_refund_workflow": False,
        "can_issue_funds": False,
        "refund_stage": "issued",
        "required_action": "none",
        "refundable_amount_cents": 4500,
        "refund_outcome": "full",
        "reasons": ["purchase_status_refunded"],
    }
    client = build_client(StubApplicationService(refund_workflow=workflow))

    response = client.post(f"/api/purchases/{PURCHASE_ID}/refund/issue")

    assert response.status_code == 200
    assert response.json()["data"] == workflow


def test_issue_refund_endpoint_reports_workflow_denial() -> None:
    client = build_client(
        StubApplicationService(error=RefundWorkflowError("Refund issuance is not allowed."))
    )

    response = client.post(f"/api/purchases/{PURCHASE_ID}/refund/issue")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "REFUND_ISSUANCE_NOT_ALLOWED",
        "message": "Refund issuance is not allowed.",
    }


def test_redeem_digital_code_endpoint_reports_workflow_denial() -> None:
    client = build_client(
        StubApplicationService(error=RefundWorkflowError("Code redemption is not allowed."))
    )

    response = client.post(f"/api/purchases/{PURCHASE_ID}/digital/redeem-code")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "CODE_REDEMPTION_NOT_ALLOWED",
        "message": "Code redemption is not allowed.",
    }


def test_redeem_digital_code_endpoint_returns_updated_detail() -> None:
    detail = {
        "purchase_id": PURCHASE_ID,
        "purchase_type": "digital",
        "details": {
            "issued_code": "DIG-RAI-10001",
            "code_redeemed": True,
            "code_redeemed_at": datetime(2026, 7, 3, 14, 30, tzinfo=UTC),
            "code_invalidated_at": None,
            "code_delivered_at": datetime(2026, 6, 20, 14, 35, tzinfo=UTC),
            "refund_window_expires_at": datetime(2026, 7, 5, 14, 30, tzinfo=UTC),
            "refund_lock_reason": "code_redeemed",
        },
    }
    client = build_client(StubApplicationService(purchase_detail=detail))

    response = client.post(f"/api/purchases/{PURCHASE_ID}/digital/redeem-code")

    assert response.status_code == 200
    assert response.json()["data"]["details"]["code_redeemed"] is True


def test_confirm_carrier_acceptance_endpoint_returns_workflow() -> None:
    workflow = build_workflow(purchase_type="physical")
    client = build_client(StubApplicationService(refund_workflow=workflow))

    response = client.post(
        f"/api/purchases/{PURCHASE_ID}/physical/confirm-carrier-acceptance"
    )

    assert response.status_code == 200
    assert response.json()["data"] == workflow


def test_confirm_carrier_acceptance_endpoint_reports_workflow_denial() -> None:
    client = build_client(
        StubApplicationService(
            error=RefundWorkflowError("Carrier acceptance confirmation is not allowed.")
        )
    )

    response = client.post(
        f"/api/purchases/{PURCHASE_ID}/physical/confirm-carrier-acceptance"
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "CARRIER_ACCEPTANCE_NOT_ALLOWED",
        "message": "Carrier acceptance confirmation is not allowed.",
    }


def test_get_refund_eligibility_endpoint_reports_missing_purchase() -> None:
    client = build_client(
        StubApplicationService(error=EntityNotFoundError("Purchase was not found."))
    )

    response = client.get(f"/api/purchases/{PURCHASE_ID}/refund/eligibility")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == {
        "code": "PURCHASE_NOT_FOUND",
        "message": "Purchase was not found.",
    }


def test_application_service_adds_purchase_details_url() -> None:
    repository = StubApplicationService(
        purchases=[{**build_purchase(), "details_url": "stale"}]
    )
    service = ApplicationService(repository)

    purchases = service.list_user_purchases(USER_ID)

    assert purchases[0]["details_url"] == f"/api/purchases/{PURCHASE_ID}/details"


def test_application_service_returns_refund_eligibility() -> None:
    service = ApplicationService(StubApplicationService())

    result = service.get_refund_eligibility(
        PURCHASE_ID,
        evaluated_at=datetime(2026, 7, 3, 14, 30, tzinfo=UTC),
    )

    assert result["purchase_id"] == PURCHASE_ID
    assert result["purchase_type"] == "digital"
    assert result["can_request_refund"] is True
    assert result["can_issue_refund"] is False
    assert result["can_prepare_refund"] is True
    assert result["refundable_amount_cents"] == 4500
    assert result["refund_outcome"] == "full"
    assert result["reasons"] == []


def test_group_user_role_rows_returns_one_payload_per_user() -> None:
    rows = [
        {
            "id": USER_ID,
            "first_name": "John",
            "last_name": "Smith",
            "created_at": USER_CREATED_AT,
            "role_key": "customer",
            "role_name": "Customer",
        },
        {
            "id": USER_ID,
            "first_name": "John",
            "last_name": "Smith",
            "created_at": USER_CREATED_AT,
            "role_key": "admin",
            "role_name": "Administrator",
        },
    ]

    users = group_user_role_rows(rows)

    assert users == [
        {
            "id": USER_ID,
            "first_name": "John",
            "last_name": "Smith",
            "created_at": USER_CREATED_AT,
            "display_name": "John Smith",
            "roles": [
                {"key": "customer", "name": "Customer"},
                {"key": "admin", "name": "Administrator"},
            ],
        }
    ]


@pytest.mark.parametrize(
    ("purchase_type", "expected_table"),
    [
        ("digital", "public.digital_purchase_details"),
        ("physical", "public.physical_purchase_details"),
        ("subscription", "public.subscription_purchase_details"),
    ],
)
def test_repository_resolves_purchase_details_table_by_purchase_type(
    purchase_type: str,
    expected_table: str,
) -> None:
    connection = StubConnection(purchase_type)
    repository = ApplicationRepository(StubConnectionProvider(connection))

    result = repository.get_purchase_detail(PURCHASE_ID)

    executed_sql = "\n".join(statement for statement, _params in connection.executed)
    assert expected_table in executed_sql
    assert result["purchase_id"] == PURCHASE_ID
    assert result["purchase_type"] == purchase_type
    assert result["details"] == connection.detail_rows[purchase_type]


def test_repository_loads_purchase_and_detail_facts_for_refund_policy() -> None:
    connection = StubConnection("physical")
    repository = ApplicationRepository(StubConnectionProvider(connection))

    result = repository.get_purchase_for_refund_policy(PURCHASE_ID)

    executed_sql = "\n".join(statement for statement, _params in connection.executed)
    assert "amount_cents" in executed_sql
    assert "status" in executed_sql
    assert "public.physical_purchase_details" in executed_sql
    assert result == {
        "purchase": connection.purchase_row,
        "detail": connection.detail_rows["physical"],
    }


def test_repository_updates_physical_refund_request_state() -> None:
    connection = StubConnection("physical")
    repository = ApplicationRepository(StubConnectionProvider(connection))

    repository.update_physical_refund_requested(PURCHASE_ID, datetime(2026, 7, 3, tzinfo=UTC))

    executed_sql = "\n".join(statement for statement, _params in connection.executed)
    assert "return_status = 'requested'" in executed_sql
    assert "return_barcode_generated = true" in executed_sql
    assert "return_status = 'not_requested'" in executed_sql
    assert "refund_requested_at" in executed_sql
    assert "status = 'refund_pending'" in executed_sql


def test_repository_raises_conflict_when_guarded_mutation_does_not_apply() -> None:
    connection = StubConnection("physical")
    connection.force_conflict = True
    repository = ApplicationRepository(StubConnectionProvider(connection))

    with pytest.raises(RepositoryConflictError):
        repository.update_physical_refund_requested(
            PURCHASE_ID,
            datetime(2026, 7, 3, tzinfo=UTC),
        )


def test_repository_updates_digital_code_redemption_state() -> None:
    connection = StubConnection("digital")
    repository = ApplicationRepository(StubConnectionProvider(connection))

    repository.update_digital_code_redeemed(PURCHASE_ID, datetime(2026, 7, 3, tzinfo=UTC))

    executed_sql = "\n".join(statement for statement, _params in connection.executed)
    assert "code_redeemed = true" in executed_sql
    assert "code_redeemed = false" in executed_sql
    assert "code_invalidated_at is null" in executed_sql
    assert "status = 'redeemed'" in executed_sql


def test_application_service_prepares_digital_refund_and_issues_funds() -> None:
    repository = StatefulWorkflowRepository("digital")
    service = ApplicationService(repository)

    prepared = service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))
    issued = service.issue_refund(PURCHASE_ID, datetime(2026, 7, 3, 15, tzinfo=UTC))

    assert prepared["refund_stage"] == "prepared"
    assert prepared["required_action"] == "issue_funds"
    assert repository.purchase["status"] == "refunded"
    assert issued["refund_stage"] == "issued"
    assert issued["refundable_amount_cents"] == 4500
    assert issued["refund_outcome"] == "full"
    assert repository.purchase["refunded_at"] == datetime(2026, 7, 3, 15, tzinfo=UTC)
    assert repository.purchase["refund_amount_cents"] == 4500
    assert repository.purchase["refund_outcome"] == "full"


def test_application_service_rejects_duplicate_refund_request() -> None:
    repository = StatefulWorkflowRepository("digital")
    service = ApplicationService(repository)
    service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))

    with pytest.raises(RefundWorkflowError, match="Refund preparation is not allowed"):
        service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 15, tzinfo=UTC))


def test_application_service_rejects_duplicate_refund_issue() -> None:
    repository = StatefulWorkflowRepository("digital")
    service = ApplicationService(repository)
    service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))
    service.issue_refund(PURCHASE_ID, datetime(2026, 7, 3, 15, tzinfo=UTC))

    with pytest.raises(RefundWorkflowError, match="Refund issuance is not allowed"):
        service.issue_refund(PURCHASE_ID, datetime(2026, 7, 3, 16, tzinfo=UTC))


def test_application_service_prepares_subscription_refund() -> None:
    repository = StatefulWorkflowRepository("subscription")
    service = ApplicationService(repository)

    result = service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))

    assert result["refund_stage"] == "prepared"
    assert repository.purchase["status"] == "refund_pending"
    assert repository.detail["cancelled_at"] == datetime(2026, 7, 3, 14, tzinfo=UTC)
    assert repository.detail["auto_renew"] is False
    assert repository.detail["refund_proration_mode"] == "full"


def test_application_service_prepares_physical_and_confirms_carrier_acceptance() -> None:
    repository = StatefulWorkflowRepository("physical")
    service = ApplicationService(repository)

    prepared = service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))
    accepted = service.confirm_carrier_acceptance(
        PURCHASE_ID,
        datetime(2026, 7, 3, 15, tzinfo=UTC),
    )

    assert prepared["required_action"] == "await_carrier_acceptance"
    assert accepted["can_issue_funds"] is True
    assert repository.detail["return_status"] == "accepted_by_carrier"


def test_application_service_rejects_duplicate_carrier_acceptance() -> None:
    repository = StatefulWorkflowRepository("physical")
    service = ApplicationService(repository)
    service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))
    service.confirm_carrier_acceptance(PURCHASE_ID, datetime(2026, 7, 3, 15, tzinfo=UTC))

    with pytest.raises(RefundWorkflowError, match="Carrier acceptance confirmation is not allowed"):
        service.confirm_carrier_acceptance(PURCHASE_ID, datetime(2026, 7, 3, 16, tzinfo=UTC))


def test_application_service_redeems_digital_code() -> None:
    repository = StatefulWorkflowRepository("digital")
    service = ApplicationService(repository)

    result = service.redeem_digital_code(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))

    assert repository.purchase["status"] == "redeemed"
    assert result["details"]["code_redeemed"] is True
    assert result["details"]["code_redeemed_at"] == datetime(2026, 7, 3, 14, tzinfo=UTC)


def test_application_service_rejects_duplicate_digital_redemption() -> None:
    repository = StatefulWorkflowRepository("digital")
    service = ApplicationService(repository)
    service.redeem_digital_code(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))

    with pytest.raises(RefundWorkflowError, match="Code redemption is not allowed"):
        service.redeem_digital_code(PURCHASE_ID, datetime(2026, 7, 3, 15, tzinfo=UTC))


def test_application_service_rejects_redemption_after_digital_invalidation() -> None:
    repository = StatefulWorkflowRepository("digital")
    service = ApplicationService(repository)
    service.request_refund(PURCHASE_ID, datetime(2026, 7, 3, 14, tzinfo=UTC))

    with pytest.raises(RefundWorkflowError, match="Code redemption is not allowed"):
        service.redeem_digital_code(PURCHASE_ID, datetime(2026, 7, 3, 15, tzinfo=UTC))


def build_workflow(purchase_type: str = "digital") -> dict[str, Any]:
    return {
        "purchase_id": PURCHASE_ID,
        "purchase_type": purchase_type,
        "can_enter_refund_workflow": True,
        "can_prepare_refund": False,
        "can_issue_funds": True,
        "refund_stage": "prepared",
        "required_action": "issue_funds",
        "refundable_amount_cents": 4500,
        "refund_outcome": "full",
        "reasons": [],
        "policy_facts": {
            "purchase_status": "refund_pending",
            "refund_window_expires_at": "2026-07-05T14:30:00Z",
            "evaluated_at": "2026-07-03T14:30:00Z",
        },
    }


class StatefulWorkflowRepository:
    def __init__(self, purchase_type: str) -> None:
        status = "subscribed" if purchase_type == "subscription" else "completed"
        self.purchase = {
            "id": PURCHASE_ID,
            "purchase_type": purchase_type,
            "amount_cents": 4500,
            "purchased_at": datetime(2026, 7, 2, 14, 0, tzinfo=UTC),
            "status": status,
            "refund_requested_at": None,
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        self.detail = self.build_detail(purchase_type)

    def list_mock_users(self) -> list[dict[str, Any]]:
        return []

    def get_user(self, user_id: str) -> dict[str, Any]:
        return build_user()

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        return []

    def get_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        return {
            "purchase_id": purchase_id,
            "purchase_type": self.purchase["purchase_type"],
            "details": self.detail,
        }

    def get_purchase_for_refund_policy(self, purchase_id: str) -> dict[str, Any]:
        return {
            "purchase": self.purchase,
            "detail": self.detail,
        }

    def update_physical_refund_requested(self, purchase_id: str, requested_at: datetime) -> None:
        if (
            self.purchase["status"] != "completed"
            or self.detail["return_status"] != "not_requested"
            or self.detail["return_requested_at"] is not None
            or self.detail["return_label_created_at"] is not None
            or self.detail["return_barcode_generated"]
        ):
            raise RepositoryConflictError("Guarded mutation conflict.")
        self.purchase["status"] = "refund_pending"
        self.purchase["refund_requested_at"] = requested_at
        self.detail["return_status"] = "requested"
        self.detail["return_requested_at"] = requested_at
        self.detail["return_barcode_generated"] = True
        self.detail["return_label_created_at"] = requested_at

    def update_digital_refund_requested(self, purchase_id: str, requested_at: datetime) -> None:
        if (
            self.purchase["status"] != "completed"
            or self.detail["code_redeemed"]
            or self.detail["code_invalidated_at"] is not None
        ):
            raise RepositoryConflictError("Guarded mutation conflict.")
        self.purchase["status"] = "refund_pending"
        self.purchase["refund_requested_at"] = requested_at
        self.detail["code_invalidated_at"] = requested_at

    def update_subscription_refund_requested(
        self,
        purchase_id: str,
        requested_at: datetime,
        refund_proration_mode: str,
    ) -> None:
        if (
            self.purchase["status"] != "subscribed"
            or self.detail["cancelled_at"] is not None
            or self.detail["service_ended_at"] is not None
            or self.detail["auto_renew"] is not True
            or self.detail["refund_proration_mode"] != "none"
        ):
            raise RepositoryConflictError("Guarded mutation conflict.")
        self.purchase["status"] = "refund_pending"
        self.purchase["refund_requested_at"] = requested_at
        self.detail["cancelled_at"] = requested_at
        self.detail["service_ended_at"] = requested_at
        self.detail["auto_renew"] = False
        self.detail["refund_proration_mode"] = refund_proration_mode

    def update_refund_issued(
        self,
        purchase_id: str,
        issued_at: datetime,
        refund_amount_cents: int,
        refund_outcome: str,
    ) -> None:
        if self.purchase["status"] != "refund_pending":
            raise RepositoryConflictError("Guarded mutation conflict.")
        self.purchase["status"] = "refunded"
        self.purchase["refunded_at"] = issued_at
        self.purchase["refund_amount_cents"] = refund_amount_cents
        self.purchase["refund_outcome"] = refund_outcome

    def update_digital_code_redeemed(self, purchase_id: str, redeemed_at: datetime) -> None:
        if (
            self.purchase["status"] != "completed"
            or self.detail["code_redeemed"]
            or self.detail["code_invalidated_at"] is not None
        ):
            raise RepositoryConflictError("Guarded mutation conflict.")
        self.purchase["status"] = "redeemed"
        self.detail["code_redeemed"] = True
        self.detail["code_redeemed_at"] = redeemed_at

    def update_physical_carrier_acceptance(self, purchase_id: str, accepted_at: datetime) -> None:
        if (
            self.purchase["status"] != "refund_pending"
            or self.detail["return_status"] != "requested"
            or not self.detail["return_barcode_generated"]
            or self.detail["return_requested_at"] is None
            or self.detail["accepted_by_carrier_at"] is not None
        ):
            raise RepositoryConflictError("Guarded mutation conflict.")
        self.detail["return_status"] = "accepted_by_carrier"
        self.detail["accepted_by_carrier_at"] = accepted_at

    def build_detail(self, purchase_type: str) -> dict[str, Any]:
        if purchase_type == "physical":
            return {
                "return_status": "not_requested",
                "return_barcode_generated": False,
                "return_label_created_at": None,
                "return_requested_at": None,
                "accepted_by_carrier_at": None,
                "refund_window_expires_at": datetime(2026, 7, 10, 14, tzinfo=UTC),
            }
        if purchase_type == "subscription":
            return {
                "period_start": datetime(2026, 7, 2, 14, tzinfo=UTC),
                "period_end": datetime(2026, 8, 1, 14, tzinfo=UTC),
                "cancelled_at": None,
                "service_ended_at": None,
                "auto_renew": True,
                "refund_proration_mode": "none",
                "full_refund_window_expires_at": datetime(2026, 7, 4, 14, tzinfo=UTC),
                "refund_window_expires_at": datetime(2026, 8, 1, 14, tzinfo=UTC),
            }
        return {
            "issued_code": "DIG-RAI-10001",
            "code_redeemed": False,
            "code_redeemed_at": None,
            "code_invalidated_at": None,
            "code_delivered_at": datetime(2026, 7, 2, 14, 5, tzinfo=UTC),
            "refund_window_expires_at": datetime(2026, 7, 10, 14, tzinfo=UTC),
            "refund_lock_reason": None,
        }

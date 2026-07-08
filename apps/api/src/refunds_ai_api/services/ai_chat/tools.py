"""Chat tool schemas and backend read-only tool execution wrappers."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.dates import (
    DEFAULT_CUSTOMER_TIMEZONE,
    InclusiveDateRange,
    build_inclusive_date_range,
    format_date,
    get_timezone,
    is_datetime_in_inclusive_date_range,
    parse_iso_date,
)
from refunds_ai_api.services.money import cents_to_dollar_string, format_cents

from .parsing import amount_matches_threshold

FULLY_REFUNDED_STATUS = "refunded"


def get_purchase_count_by_amount_threshold_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for deterministic threshold purchase counts."""
    return {
        "name": "get_purchase_count_by_amount_threshold",
        "description": (
            "Count a customer's purchases that match an amount threshold using "
            "backend purchase data. Fully refunded purchases are excluded from "
            "aggregate counts and totals; refunds still in progress remain included."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "threshold_cents": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Purchase amount threshold in cents.",
                },
                "comparison": {
                    "type": "string",
                    "enum": ["gt", "gte", "lt", "lte"],
                    "description": "Comparison to apply against purchase amount.",
                },
            },
            "required": ["threshold_cents", "comparison"],
            "additionalProperties": False,
        },
    }


def get_purchase_history_by_date_range_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for deterministic date-range purchase history."""
    return {
        "name": "get_purchase_history_by_date_range",
        "description": (
            "Retrieve a customer's purchases and aggregate totals for an inclusive "
            "local date range. Fully refunded purchases are excluded from aggregate "
            "counts and totals; refunds still in progress remain included."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Inclusive local start date in YYYY-MM-DD format.",
                },
                "end_date": {
                    "type": "string",
                    "description": "Inclusive local end date in YYYY-MM-DD format.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Customer timezone, such as America/Chicago.",
                },
            },
            "required": ["start_date", "end_date", "timezone"],
            "additionalProperties": False,
        },
    }


def get_refund_policy_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for deterministic refund policy lookup."""
    return {
        "name": "get_refund_policy",
        "description": (
            "Retrieve read-only RefundsAI refund policy sections scoped to the "
            "customer's policy question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": [
                        "general",
                        "product_type",
                        "funds_release",
                        "administrative_review",
                    ],
                    "description": "Policy lookup scope needed to answer the question.",
                },
                "purchase_type": {
                    "type": "string",
                    "enum": ["digital", "physical", "subscription"],
                    "description": "Optional product type when the question names one.",
                },
            },
            "required": ["scope"],
            "additionalProperties": False,
        },
    }


def get_refund_eligibility_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for read-only backend refund eligibility."""
    return {
        "name": "get_refund_eligibility",
        "description": (
            "Evaluate read-only refund eligibility for backend-resolved purchase ids. "
            "This tool does not start, prepare, submit, process, or issue refunds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "purchase_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Purchase ids already resolved by the backend chat graph.",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Small context label such as product, digital, current_page, "
                        "selected_set, date_range, or all_purchases."
                    ),
                },
            },
            "required": ["purchase_ids"],
            "additionalProperties": False,
        },
    }


def get_customer_purchase_history_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for the purchase-history reader."""
    return {
        "name": "get_customer_purchase_history",
        "description": (
            "Retrieve read-only purchase history and aggregate totals for one customer. "
            "The result includes a history summary that counts all historical "
            "purchases and splits refunded versus non-refunded purchases. Aggregate "
            "spend/count fields still exclude fully refunded purchases; refunds "
            "still in progress remain included."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    }


def validate_customer_account_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for the active mock customer reader."""
    return {
        "name": "validate_customer_account",
        "description": (
            "Read the active mock customer account from backend data. The active "
            "request supplies the customer id; the model must not provide or choose it."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    }


def validate_customer_account(
    application_service: ApplicationService,
    customer_id: str,
) -> dict[str, Any]:
    """Return sanitized active mock customer metadata."""
    try:
        user = application_service.get_user(customer_id)
    except Exception:
        return {
            "customer_id": customer_id,
            "valid": False,
            "display_name": None,
            "first_name": None,
            "last_name": None,
            "roles": [],
        }
    roles = user.get("roles")
    if not isinstance(roles, list):
        roles = []
    return {
        "customer_id": str(user.get("id", customer_id)),
        "valid": True,
        "display_name": user.get("display_name"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "roles": [
            {
                "key": role.get("key"),
                "name": role.get("name"),
            }
            for role in roles
            if isinstance(role, dict)
        ],
    }


def get_customer_purchase_history(
    application_service: ApplicationService,
    customer_id: str,
) -> dict[str, Any]:
    """Return sanitized purchase rows and deterministic aggregates."""
    purchases = application_service.list_user_purchases(customer_id)
    timezone = get_timezone(DEFAULT_CUSTOMER_TIMEZONE)
    rows = [build_purchase_tool_row(purchase, timezone) for purchase in purchases]
    aggregate_rows = filter_aggregate_eligible_purchase_rows(rows)

    return {
        "customer_id": customer_id,
        "purchases": rows,
        "history_summary": build_purchase_history_summary(rows),
        "aggregates": build_purchase_history_aggregates(aggregate_rows),
    }


def get_purchase_history_by_date_range(
    application_service: ApplicationService,
    customer_id: str,
    *,
    start_date: str,
    end_date: str,
    timezone_name: str,
    label: str | None = None,
) -> dict[str, Any]:
    """Return deterministic purchase history and totals for one inclusive date range."""
    timezone = get_timezone(timezone_name)
    date_range = build_inclusive_date_range(
        start_date=parse_iso_date(start_date),
        end_date=parse_iso_date(end_date),
        timezone=timezone,
        label=label,
    )
    purchases = application_service.list_user_purchases(customer_id)
    rows = [
        build_purchase_tool_row(purchase, timezone)
        for purchase in purchases
        if is_datetime_in_inclusive_date_range(purchase["purchased_at"], date_range)
    ]
    aggregate_rows = filter_aggregate_eligible_purchase_rows(rows)

    return {
        "customer_id": customer_id,
        "date_range": build_date_range_output(date_range),
        "history_summary": build_purchase_history_summary(rows),
        "aggregates": build_purchase_history_aggregates(aggregate_rows),
        "purchases": rows,
    }


def get_purchase_count_by_amount_threshold(
    application_service: ApplicationService,
    customer_id: str,
    *,
    threshold_cents: int,
    comparison: str,
) -> dict[str, Any]:
    """Return deterministic purchase count and totals for one amount threshold."""
    purchases = application_service.list_user_purchases(customer_id)
    matching_purchases = [
        purchase
        for purchase in purchases
        if is_purchase_aggregate_eligible(purchase)
        and amount_matches_threshold(
            int(purchase["amount_cents"]),
            threshold_cents,
            comparison,
        )
    ]
    total_amount_cents = sum(int(purchase["amount_cents"]) for purchase in matching_purchases)
    return {
        "count": len(matching_purchases),
        "matching_purchase_ids": [str(purchase["id"]) for purchase in matching_purchases],
        "total_amount_cents": total_amount_cents,
        "total_amount_dollars": cents_to_dollar_string(total_amount_cents),
        "threshold_cents": threshold_cents,
        "threshold_dollars": cents_to_dollar_string(threshold_cents),
        "comparison": comparison,
    }


def get_refund_eligibility(
    application_service: ApplicationService,
    customer_id: str,
    *,
    purchase_ids: list[str],
    context: str,
) -> dict[str, Any]:
    """Return backend-evaluated read-only refund eligibility for active purchases."""
    active_purchases = {
        str(purchase["id"]): purchase
        for purchase in application_service.list_user_purchases(customer_id)
    }
    resolved_purchase_ids = [
        purchase_id
        for purchase_id in dict.fromkeys(purchase_ids)
        if isinstance(purchase_id, str) and purchase_id in active_purchases
    ]
    rows: list[dict[str, Any]] = []
    timezone = get_timezone(DEFAULT_CUSTOMER_TIMEZONE)

    for purchase_id in resolved_purchase_ids:
        purchase = active_purchases[purchase_id]
        workflow = application_service.get_refund_workflow(purchase_id)
        amount_cents = int(purchase["amount_cents"])
        refundable_amount_cents = int(workflow["refundable_amount_cents"])
        rows.append(
            {
                "id": purchase_id,
                "order_number": purchase["order_number"],
                "sku": purchase.get("sku"),
                "product_name": purchase["product_name"],
                "purchase_type": purchase["purchase_type"],
                "status": purchase["status"],
                "amount_cents": amount_cents,
                "amount_dollars": cents_to_dollar_string(amount_cents),
                "amount_display": format_cents(amount_cents),
                "purchased_at": purchase["purchased_at"],
                "purchased_date_display": format_date(purchase["purchased_at"], timezone),
                "refund_stage": workflow["refund_stage"],
                "can_enter_refund_workflow": workflow["can_enter_refund_workflow"],
                "can_prepare_refund": workflow["can_prepare_refund"],
                "can_issue_funds": workflow["can_issue_funds"],
                "required_action": workflow["required_action"],
                "refund_outcome": workflow["refund_outcome"],
                "refundable_amount_cents": refundable_amount_cents,
                "refundable_amount_dollars": cents_to_dollar_string(refundable_amount_cents),
                "refundable_amount_display": format_cents(refundable_amount_cents),
                "reasons": workflow["reasons"],
                "policy_facts": workflow["policy_facts"],
            }
        )

    return {
        "customer_id": customer_id,
        "context": context,
        "requested_purchase_ids": purchase_ids,
        "resolved_purchase_ids": resolved_purchase_ids,
        "purchase_count": len(rows),
        "eligible_count": sum(
            1 for row in rows if row["can_enter_refund_workflow"] is True
        ),
        "blocked_count": sum(1 for row in rows if row["refund_stage"] == "blocked"),
        "prepared_count": sum(1 for row in rows if row["refund_stage"] == "prepared"),
        "issued_count": sum(1 for row in rows if row["refund_stage"] == "issued"),
        "purchases": rows,
    }


def build_purchase_tool_row(
    purchase: dict[str, Any],
    timezone: ZoneInfo,
) -> dict[str, Any]:
    """Return a sanitized purchase row for model-facing account tool payloads."""
    amount_cents = int(purchase["amount_cents"])
    purchased_at = purchase["purchased_at"]
    return {
        "id": str(purchase["id"]),
        "order_number": purchase["order_number"],
        "purchase_type": purchase["purchase_type"],
        "product_name": purchase["product_name"],
        "amount_cents": amount_cents,
        "amount_dollars": cents_to_dollar_string(amount_cents),
        "amount_display": format_cents(amount_cents),
        "purchased_at": purchased_at,
        "purchased_date_display": format_date(purchased_at, timezone),
        "status": purchase["status"],
    }


def is_purchase_aggregate_eligible(purchase: dict[str, Any]) -> bool:
    """Return whether a purchase should contribute to count and spend aggregates."""
    return purchase.get("status") != FULLY_REFUNDED_STATUS


def filter_aggregate_eligible_purchase_rows(
    purchases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return purchase rows that should contribute to count and spend aggregates."""
    return [purchase for purchase in purchases if is_purchase_aggregate_eligible(purchase)]


def build_date_range_output(date_range: InclusiveDateRange) -> dict[str, str]:
    """Return model-facing metadata for an inclusive date range."""
    return {
        "start_date": date_range.start_date.isoformat(),
        "end_date": date_range.end_date.isoformat(),
        "label": date_range.label,
        "timezone": str(date_range.timezone),
    }


def build_purchase_history_aggregates(purchases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute purchase-history counts and totals for model consumption."""
    by_purchase_type: dict[str, dict[str, Any]] = {}
    by_status: dict[str, dict[str, Any]] = {}
    total_amount_cents = 0

    for purchase in purchases:
        amount_cents = int(purchase["amount_cents"])
        total_amount_cents += amount_cents

        increment_aggregate_bucket(by_purchase_type, purchase["purchase_type"], amount_cents)
        increment_aggregate_bucket(by_status, purchase["status"], amount_cents)

    return {
        "total_purchase_count": len(purchases),
        "total_amount_cents": total_amount_cents,
        "total_amount_dollars": cents_to_dollar_string(total_amount_cents),
        "by_purchase_type": by_purchase_type,
        "by_status": by_status,
    }


def build_purchase_history_summary(purchases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute historical purchase counts with refunded/non-refunded splits."""
    by_purchase_type: dict[str, dict[str, Any]] = {}
    by_status: dict[str, dict[str, Any]] = {}
    refunded_count = 0
    non_refunded_count = 0

    for purchase in purchases:
        status = purchase["status"]
        purchase_type = purchase["purchase_type"]
        is_refunded = status == FULLY_REFUNDED_STATUS
        if is_refunded:
            refunded_count += 1
        else:
            non_refunded_count += 1

        increment_history_bucket(by_purchase_type, purchase_type, is_refunded)
        increment_history_bucket(by_status, status, is_refunded)

    return {
        "total_purchase_count": len(purchases),
        "non_refunded_purchase_count": non_refunded_count,
        "refunded_purchase_count": refunded_count,
        "by_purchase_type": by_purchase_type,
        "by_status": by_status,
    }


def increment_aggregate_bucket(
    buckets: dict[str, dict[str, Any]],
    key: str,
    amount_cents: int,
) -> None:
    """Increment one count/amount aggregate bucket."""
    bucket = buckets.setdefault(key, {"count": 0, "total_amount_cents": 0})
    bucket["count"] += 1
    bucket["total_amount_cents"] += amount_cents
    bucket["total_amount_dollars"] = cents_to_dollar_string(bucket["total_amount_cents"])


def increment_history_bucket(
    buckets: dict[str, dict[str, Any]],
    key: str,
    is_refunded: bool,
) -> None:
    """Increment one historical count bucket with refund split fields."""
    bucket = buckets.setdefault(
        key,
        {
            "total_count": 0,
            "non_refunded_count": 0,
            "refunded_count": 0,
        },
    )
    bucket["total_count"] += 1
    if is_refunded:
        bucket["refunded_count"] += 1
    else:
        bucket["non_refunded_count"] += 1

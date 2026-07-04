"""Response models for frontend-facing user and purchase read APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoleRead(BaseModel):
    """Role metadata returned with mock users."""

    model_config = ConfigDict(extra="forbid")

    key: str
    name: str


class UserRead(BaseModel):
    """Selectable mock user payload."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    first_name: str
    last_name: str
    created_at: datetime
    display_name: str
    roles: list[RoleRead]


class PurchaseSummaryRead(BaseModel):
    """Purchase history row suitable for frontend list rendering."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    order_number: str
    purchase_type: Literal["physical", "digital", "subscription"]
    product_name: str
    sku: str
    amount_cents: int
    purchased_at: datetime
    status: str
    details_url: str


class PurchaseDetailsRead(BaseModel):
    """Purchase detail response with backend-resolved type-specific fields."""

    model_config = ConfigDict(extra="forbid")

    purchase_id: UUID
    purchase_type: Literal["physical", "digital", "subscription"]
    details: dict[str, Any]


class RefundEligibilityRead(BaseModel):
    """Backend-evaluated refund workflow response."""

    model_config = ConfigDict(extra="forbid")

    purchase_id: UUID
    purchase_type: Literal["physical", "digital", "subscription"]
    can_enter_refund_workflow: bool
    can_prepare_refund: bool
    can_issue_funds: bool
    refund_stage: Literal["blocked", "eligible", "prepared", "issued"]
    required_action: Literal[
        "none",
        "request_refund",
        "invalidate_code",
        "generate_return_label",
        "cancel_subscription",
        "await_carrier_acceptance",
        "issue_funds",
    ]
    refundable_amount_cents: int
    refund_outcome: Literal["none", "full", "prorated"]
    reasons: list[str]
    policy_facts: dict[str, Any]

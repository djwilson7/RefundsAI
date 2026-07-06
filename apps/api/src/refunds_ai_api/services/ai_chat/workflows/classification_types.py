"""Shared workflow classification enums."""

from __future__ import annotations

from enum import StrEnum


class WorkflowKind(StrEnum):
    """Supported deterministic chat workflow families."""

    ACCOUNT_FACT = "account_fact"
    REFUND_POLICY = "refund_policy"
    REFUND_ELIGIBILITY = "refund_eligibility"
    REFUND_MUTATION = "refund_mutation"
    OFF_DOMAIN = "off_domain"

"""Money conversion helpers for cent-based backend storage."""

from __future__ import annotations

from decimal import Decimal


def dollars_to_cents(amount: Decimal | float | int) -> int:
    """Convert a dollar-denominated amount into integer cents."""
    return int(Decimal(str(amount)) * 100)


def cents_to_dollars(cents: int) -> Decimal:
    """Convert integer cents into a dollar-denominated Decimal."""
    return Decimal(cents) / Decimal("100")


def cents_to_dollar_string(cents: int) -> str:
    """Return a stable two-decimal dollar string for model-facing payloads."""
    return f"{cents_to_dollars(cents):.2f}"


def format_cents(cents: int) -> str:
    """Return a currency display string for model-facing payloads."""
    return f"${cents_to_dollar_string(cents)}"

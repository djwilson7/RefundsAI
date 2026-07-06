"""Chat-specific date range parsing and date-range labels."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from refunds_ai_api.services.dates import (
    DEFAULT_CUSTOMER_TIMEZONE,
    build_inclusive_date_range,
    get_timezone,
    parse_iso_date,
)

from .routing import has_account_fact_intent


def parse_date_range_query(
    message: str,
    *,
    today: date | None = None,
    timezone_name: str = DEFAULT_CUSTOMER_TIMEZONE,
) -> dict[str, str] | None:
    """Parse narrow purchase date-range questions into deterministic tool args."""
    normalized_message = message.casefold()
    if not has_account_fact_intent(normalized_message):
        return None

    timezone = get_timezone(timezone_name)
    reference_date = today or datetime.now(timezone).date()

    try:
        last_week_range = parse_relative_week_range(normalized_message, reference_date)
        if last_week_range is not None:
            start_date, end_date, label = last_week_range
            return date_range_query(start_date, end_date, timezone_name, label)

        month_day_range = parse_month_day_range(normalized_message, reference_date.year)
        if month_day_range is not None:
            start_date, end_date, label = month_day_range
            return date_range_query(start_date, end_date, timezone_name, label)

        first_week_range = parse_first_week_of_month(normalized_message, reference_date.year)
        if first_week_range is not None:
            start_date, end_date, label = first_week_range
            return date_range_query(start_date, end_date, timezone_name, label)

        month_range = parse_month_range(normalized_message, reference_date.year)
        if month_range is not None:
            start_date, end_date, label = month_range
            return date_range_query(start_date, end_date, timezone_name, label)
    except ValueError:
        return None

    return None


def parse_relative_week_range(
    message: str,
    reference_date: date,
) -> tuple[date, date, str] | None:
    """Parse supported relative week phrases."""
    days_since_sunday = (reference_date.weekday() + 1) % 7
    current_week_start = reference_date - timedelta(days=days_since_sunday)
    if "last week" in message:
        start_date = current_week_start - timedelta(days=7)
        end_date = start_date + timedelta(days=6)
        return start_date, end_date, "last week"
    if "this week" in message:
        start_date = current_week_start
        end_date = reference_date
        return start_date, end_date, "this week"
    return None


def parse_first_week_of_month(
    message: str,
    default_year: int,
) -> tuple[date, date, str] | None:
    """Parse 'first week of Month' as Month 1 through Month 7."""
    match = re.search(r"\bfirst week of\s+([a-z]+)(?:\s+(\d{4}))?\b", message)
    if match is None:
        return None

    month_number = parse_month_name(match.group(1))
    if month_number is None:
        return None

    year = int(match.group(2) or default_year)
    start_date = date(year, month_number, 1)
    end_date = date(year, month_number, 7)
    return start_date, end_date, f"first week of {format_month_name(month_number)} {year}"


def parse_month_day_range(
    message: str,
    default_year: int,
) -> tuple[date, date, str] | None:
    """Parse 'May 1 to May 7', 'between June 1 and June 15', and 'on July 4'."""
    range_match = re.search(
        r"\b(?:between\s+)?([a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?\s+"
        r"(?:to|through|and|-)\s+(?:(?:([a-z]+)\s+)?(\d{1,2})(?:,\s*(\d{4}))?)\b",
        message,
    )
    if range_match is not None:
        start_month = parse_month_name(range_match.group(1))
        if start_month is None:
            return None

        end_month = parse_month_name(range_match.group(4)) if range_match.group(4) else start_month
        if end_month is None:
            return None

        start_year = int(range_match.group(3) or default_year)
        end_year = int(range_match.group(6) or start_year)
        start_date = date(start_year, start_month, int(range_match.group(2)))
        end_date = date(end_year, end_month, int(range_match.group(5)))
        return start_date, end_date, format_date_range_label_for_query(start_date, end_date)

    on_match = re.search(r"\bon\s+([a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?\b", message)
    if on_match is None:
        return None

    month_number = parse_month_name(on_match.group(1))
    if month_number is None:
        return None

    matched_date = date(
        int(on_match.group(3) or default_year),
        month_number,
        int(on_match.group(2)),
    )
    return matched_date, matched_date, format_date_range_label_for_query(matched_date, matched_date)


def parse_month_range(
    message: str,
    default_year: int,
) -> tuple[date, date, str] | None:
    """Parse 'in May' as the full calendar month."""
    match = re.search(r"\bin\s+([a-z]+)(?:\s+(\d{4}))?\b", message)
    if match is None:
        return None

    month_number = parse_month_name(match.group(1))
    if month_number is None:
        return None

    year = int(match.group(2) or default_year)
    start_date = date(year, month_number, 1)
    if month_number == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, month_number + 1, 1) - timedelta(days=1)
    return start_date, end_date, f"{format_month_name(month_number)} {year}"


def date_range_query(
    start_date: date,
    end_date: date,
    timezone_name: str,
    label: str,
) -> dict[str, str]:
    """Return date-range tool arguments with ISO dates."""
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": timezone_name,
        "label": label,
    }


def parse_month_name(value: str) -> int | None:
    """Return a month number for supported English month names."""
    months = {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12,
    }
    return months.get(value.casefold())


def format_month_name(month_number: int) -> str:
    """Return an English month name."""
    return date(2000, month_number, 1).strftime("%B")


def format_date_range_label_for_query(start_date: date, end_date: date) -> str:
    """Return a stable date-range label for parsed queries."""
    if start_date == end_date:
        return f"{format_month_name(start_date.month)} {start_date.day}, {start_date.year}"
    return (
        f"{format_month_name(start_date.month)} {start_date.day}, {start_date.year} "
        f"through {format_month_name(end_date.month)} {end_date.day}, {end_date.year}"
    )


def parse_model_date_range_arguments(arguments: dict[str, Any]) -> dict[str, str] | None:
    """Validate model-provided date-range arguments before tool execution."""
    start_date_value = arguments.get("start_date")
    end_date_value = arguments.get("end_date")
    timezone_value = arguments.get("timezone") or DEFAULT_CUSTOMER_TIMEZONE
    if not isinstance(start_date_value, str) or not isinstance(end_date_value, str):
        return None
    if not isinstance(timezone_value, str):
        return None

    try:
        start_date = parse_iso_date(start_date_value)
        end_date = parse_iso_date(end_date_value)
        build_inclusive_date_range(
            start_date=start_date,
            end_date=end_date,
            timezone=get_timezone(timezone_value),
        )
    except ValueError:
        return None

    label = arguments.get("label") or format_date_range_label_for_query(start_date, end_date)
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": timezone_value,
        "label": str(label),
    }

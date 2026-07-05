"""Date normalization and display helpers for account tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_CUSTOMER_TIMEZONE = "America/Chicago"


@dataclass(frozen=True)
class InclusiveDateRange:
    """Inclusive local date range with half-open UTC timestamp bounds."""

    start_date: date
    end_date: date
    timezone: ZoneInfo
    start_at_utc: datetime
    end_before_utc: datetime
    label: str


def get_timezone(timezone_name: str | None) -> ZoneInfo:
    """Return a configured timezone, falling back to the customer default."""
    try:
        return ZoneInfo(timezone_name or DEFAULT_CUSTOMER_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_CUSTOMER_TIMEZONE)


def parse_iso_date(value: str) -> date:
    """Parse an ISO calendar date."""
    return date.fromisoformat(value)


def build_inclusive_date_range(
    *,
    start_date: date,
    end_date: date,
    timezone: ZoneInfo,
    label: str | None = None,
) -> InclusiveDateRange:
    """Build inclusive local dates and half-open UTC timestamp bounds."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date.")

    start_at_local = datetime.combine(start_date, time.min, tzinfo=timezone)
    end_before_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone)
    return InclusiveDateRange(
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        start_at_utc=start_at_local.astimezone(UTC),
        end_before_utc=end_before_local.astimezone(UTC),
        label=label or format_date_range_label(start_date, end_date),
    )


def is_datetime_in_inclusive_date_range(
    value: datetime,
    date_range: InclusiveDateRange,
) -> bool:
    """Return whether a timestamp falls within an inclusive local date range."""
    value_utc = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return date_range.start_at_utc <= value_utc < date_range.end_before_utc


def format_date(value: date | datetime, timezone: ZoneInfo) -> str:
    """Return a cross-platform friendly date display string."""
    if isinstance(value, datetime):
        local_date = value.astimezone(timezone).date() if value.tzinfo else value.date()
    else:
        local_date = value

    month_name = datetime.combine(local_date, time.min).strftime("%B")
    return f"{month_name} {local_date.day}, {local_date.year}"


def format_date_range_label(start_date: date, end_date: date) -> str:
    """Return a readable label for an inclusive date range."""
    if start_date == end_date:
        return format_date(start_date, ZoneInfo("UTC"))
    return (
        f"{format_date(start_date, ZoneInfo('UTC'))} through "
        f"{format_date(end_date, ZoneInfo('UTC'))}"
    )

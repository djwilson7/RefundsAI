"""YAML-like trace block formatting primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .helpers import MAX_TRACE_ITEMS


def format_debug_block(title: str, data: Mapping[str, Any]) -> str:
    """Format one stable YAML-like debug block."""
    lines = [f"--- {title} ---"]
    lines.extend(_format_mapping(data, indent=0))
    lines.append(f"--- end {title} ---")
    return "\n".join(lines)

def format_sequence_block(title: str, items: Sequence[Any]) -> str:
    """Format one bounded list block."""
    return format_debug_block(title, {"items": list(items)})

def _format_mapping(data: Mapping[str, Any], *, indent: int) -> list[str]:
    lines: list[str] = []
    for key, value in data.items():
        lines.extend(_format_value(str(key), value, indent=indent))
    return lines

def _format_value(key: str, value: Any, *, indent: int) -> list[str]:
    prefix = " " * indent
    if value is None:
        return [f"{prefix}{key}: null"]
    if isinstance(value, Mapping):
        visible_items = {item_key: item_value for item_key, item_value in value.items()}
        if not visible_items:
            return [f"{prefix}{key}: {{}}"]
        lines = [f"{prefix}{key}:"]
        lines.extend(_format_mapping(visible_items, indent=indent + 2))
        return lines
    if isinstance(value, list | tuple):
        return _format_sequence(key, value, indent=indent)
    return [f"{prefix}{key}: {value}"]

def _format_sequence(key: str, value: Sequence[Any], *, indent: int) -> list[str]:
    prefix = " " * indent
    if not value:
        return [f"{prefix}{key}: []"]
    lines = [f"{prefix}{key}:"]
    visible_items = list(value[:MAX_TRACE_ITEMS])
    for item in visible_items:
        item_prefix = " " * (indent + 2)
        if isinstance(item, Mapping):
            lines.append(f"{item_prefix}-")
            lines.extend(_format_mapping(item, indent=indent + 4))
        else:
            lines.append(f"{item_prefix}- {item}")
    remaining = len(value) - len(visible_items)
    if remaining > 0:
        lines.append(f"{' ' * (indent + 2)}... {remaining} more items not shown")
    return lines

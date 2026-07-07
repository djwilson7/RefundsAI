"""Current-page reference resolution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.state import normalize_page_context
from refunds_ai_api.services.application import ApplicationService

from .purchases import resolve_purchase_by_id


def resolve_page_reference(
    application_service: ApplicationService | None,
    customer_id: str | None,
    page_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve the current page to a small backend-grounded reference."""
    normalized_context = normalize_page_context(page_context)
    if normalized_context["surface"] != "purchase_detail":
        return {"surface": "purchase_history", "purchase": None}

    purchase = resolve_purchase_by_id(
        application_service,
        customer_id,
        normalized_context["purchase_id"],
    )
    if purchase is None:
        return {"surface": "purchase_detail", "purchase": None}

    return {"surface": "purchase_detail", "purchase": purchase}

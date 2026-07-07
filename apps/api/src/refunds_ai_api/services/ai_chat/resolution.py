"""Compatibility facade for AI chat resolution helpers."""

from __future__ import annotations

# ruff: noqa: F401
from .resolvers.eligibility import (
    resolve_policy_follow_up_eligibility,
    resolve_refund_eligibility_query,
)
from .resolvers.facts import (
    build_resolved_purchase_fact,
    resolve_purchase_fact_by_id,
    resolve_purchase_fact_context,
    resolve_purchase_reference_fact,
    resolve_ranked_purchase_context,
)
from .resolvers.page import resolve_page_reference
from .resolvers.policy import (
    resolve_refund_policy_query,
    resolve_refund_policy_query_with_purchase,
)
from .resolvers.products import (
    build_unresolved_product_response,
    clean_product_reference,
    explicit_purchase_type_word,
    extract_product_reference,
    is_demonstrative_product_reference,
    is_generic_purchase_type_reference,
    is_named_product_reference,
    normalize_match_text,
)
from .resolvers.purchases import (
    build_resolved_purchase,
    match_purchase_reference,
    purchase_search_values,
    resolve_global_ranked_purchase,
    resolve_purchase_by_id,
    resolve_purchase_from_selected_set,
    resolve_purchase_mention,
    resolve_purchase_reference,
    resolve_purchase_reference_for_state,
    resolve_selected_single_purchase,
)

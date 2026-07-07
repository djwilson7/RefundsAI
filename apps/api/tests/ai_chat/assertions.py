from __future__ import annotations

from refunds_ai_api.services.ai_chat import contains_forbidden_customer_response_term


def assert_refund_command_response(
    content: str,
    expected_prefix: str,
    expected_command: str,
) -> None:
    assert content.startswith(expected_prefix)
    assert expected_command in content
    assert not contains_forbidden_customer_response_term(content)

def assert_customer_safe_response(content: str) -> None:
    assert not contains_forbidden_customer_response_term(content)

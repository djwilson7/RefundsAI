from fastapi.testclient import TestClient

from refunds_ai_api.main import create_app
from refunds_ai_api.routes.chat import PLACEHOLDER_RESPONSE


def test_chat_endpoint_returns_static_phase_one_response() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/chat",
        json={
            "message": "How many digital purchases have I made?",
            "customer_id": "10000000-0000-4000-8000-000000000001",
            "purchase_id": "40000000-0000-4000-8000-000000000001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "message": {
            "role": "assistant",
            "content": PLACEHOLDER_RESPONSE,
        },
        "model": "gpt-5.4-mini",
        "graph_ready": False,
    }
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_chat_endpoint_rejects_empty_messages() -> None:
    client = TestClient(create_app())

    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == {
        "code": "INVALID_CHAT_MESSAGE",
        "message": "Chat message must not be empty.",
    }
    assert "timestamp" in body["meta"]


def test_chat_endpoint_rejects_missing_messages() -> None:
    client = TestClient(create_app())

    response = client.post("/api/chat", json={})

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "INVALID_CHAT_MESSAGE",
        "message": "Chat message must not be empty.",
    }


def test_chat_endpoint_emits_structured_log_events(caplog) -> None:
    client = TestClient(create_app())

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        response = client.post(
            "/api/chat",
            json={
                "message": "Show my purchases",
                "customer_id": "10000000-0000-4000-8000-000000000001",
                "purchase_id": "40000000-0000-4000-8000-000000000001",
            },
        )

    assert response.status_code == 200
    events = [record.event for record in caplog.records]
    assert events == [
        {
            "type": "message.received",
            "message_length": len("Show my purchases"),
            "customer_id": "10000000-0000-4000-8000-000000000001",
            "purchase_id": "40000000-0000-4000-8000-000000000001",
        },
        {
            "type": "response.generated",
            "model": "gpt-5.4-mini",
            "graph_ready": False,
        },
    ]


def test_openapi_documents_chat_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/chat" in response.json()["paths"]

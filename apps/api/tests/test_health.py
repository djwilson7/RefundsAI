from fastapi.testclient import TestClient

from refunds_ai_api.main import create_app


def test_startup_logs_host_friendly_urls(caplog) -> None:
    with caplog.at_level("INFO", logger="uvicorn.error"):
        with TestClient(create_app()):
            pass

    messages = [record.message for record in caplog.records]
    assert "RefundsAI API" in messages
    assert "- Local:   http://localhost:8000" in messages
    assert "- Docs:    http://localhost:8000/docs" in messages
    assert "- Network: http://0.0.0.0:8000" in messages


def test_health_endpoint_returns_standard_response() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "service": "refunds-ai-api",
        "status": "ok",
    }
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_openapi_documents_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]

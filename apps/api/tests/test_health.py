from fastapi.testclient import TestClient

from refunds_ai_api.config import Settings
from refunds_ai_api.main import create_app
from refunds_ai_api.routes.health import get_model_health_checker
from refunds_ai_api.services.model_health import (
    ModelConnectionError,
    ModelHealth,
    OpenAIModelHealthChecker,
)


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


class StubModelHealthChecker:
    def __init__(self, result: ModelHealth | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def check(self) -> ModelHealth:
        if self.error:
            raise self.error
        if self.result is None:
            raise AssertionError("Stub model health result was not configured.")
        return self.result


def build_model_health_client(checker: StubModelHealthChecker) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_model_health_checker] = lambda: checker
    return TestClient(app)


def test_model_health_endpoint_returns_connected_model_state() -> None:
    client = build_model_health_client(
        StubModelHealthChecker(
            ModelHealth(
                provider="openai",
                configured=True,
                connected=True,
                model="gpt-5.4-mini",
                detail="OpenAI model handshake succeeded.",
            )
        )
    )

    response = client.get("/health/model")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "provider": "openai",
        "configured": True,
        "connected": True,
        "model": "gpt-5.4-mini",
    }
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_model_health_endpoint_reports_missing_api_key() -> None:
    client = build_model_health_client(
        StubModelHealthChecker(
            ModelHealth(
                provider="openai",
                configured=False,
                connected=False,
                model="gpt-5.4-mini",
                detail="OPENAI_API_KEY is not configured.",
            )
        )
    )

    response = client.get("/health/model")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"] == {
        "provider": "openai",
        "configured": False,
        "connected": False,
        "model": "gpt-5.4-mini",
    }
    assert body["error"] == {
        "code": "MODEL_NOT_CONFIGURED",
        "message": "OPENAI_API_KEY is not configured.",
    }


def test_model_health_endpoint_reports_connection_failure() -> None:
    client = build_model_health_client(
        StubModelHealthChecker(error=ModelConnectionError("OpenAI model handshake failed."))
    )

    response = client.get("/health/model")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == {
        "code": "MODEL_CONNECTION_FAILED",
        "message": "OpenAI model handshake failed.",
    }


def test_openapi_documents_model_health_endpoint() -> None:
    client = build_model_health_client(
        StubModelHealthChecker(
            ModelHealth(
                provider="openai",
                configured=True,
                connected=True,
                model="gpt-5.4-mini",
                detail="OpenAI model handshake succeeded.",
            )
        )
    )

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health/model" in response.json()["paths"]


def test_openai_model_health_checker_reports_missing_configuration() -> None:
    checker = OpenAIModelHealthChecker(
        Settings(
            OPENAI_API_KEY=None,
            OPENAI_MODEL="gpt-5.4-mini",
        )
    )

    assert checker.check() == ModelHealth(
        provider="openai",
        configured=False,
        connected=False,
        model="gpt-5.4-mini",
        detail="OPENAI_API_KEY is not configured.",
    )


def test_openai_model_health_checker_reports_success(monkeypatch) -> None:
    class StubCompletions:
        def create(self, **kwargs) -> dict[str, str]:
            return {"id": "chatcmpl-test"}

    completions = StubCompletions()
    chat = type("Chat", (), {"completions": completions})()

    class StubOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.chat = chat

    monkeypatch.setattr("refunds_ai_api.services.model_health.OpenAI", StubOpenAI)

    checker = OpenAIModelHealthChecker(
        Settings(
            OPENAI_API_KEY="sk-test",
            OPENAI_MODEL="gpt-5.4-mini",
        )
    )

    assert checker.check() == ModelHealth(
        provider="openai",
        configured=True,
        connected=True,
        model="gpt-5.4-mini",
        detail="OpenAI model handshake succeeded.",
    )


def test_openai_model_health_checker_wraps_handshake_errors(monkeypatch) -> None:
    class StubCompletions:
        def create(self, **kwargs) -> None:
            raise RuntimeError("network unavailable")

    completions = StubCompletions()
    chat = type("Chat", (), {"completions": completions})()

    class StubOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.chat = chat

    monkeypatch.setattr("refunds_ai_api.services.model_health.OpenAI", StubOpenAI)

    checker = OpenAIModelHealthChecker(
        Settings(
            OPENAI_API_KEY="sk-test",
            OPENAI_MODEL="gpt-5.4-mini",
        )
    )

    try:
        checker.check()
    except ModelConnectionError as exc:
        assert str(exc) == "OpenAI model handshake failed."
        assert isinstance(exc.__cause__, RuntimeError)
    else:
        raise AssertionError("Expected ModelConnectionError.")

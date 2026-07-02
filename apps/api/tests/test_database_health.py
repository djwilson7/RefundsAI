import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from refunds_ai_api.config import Settings
from refunds_ai_api.main import create_app
from refunds_ai_api.routes.health import get_database_health_checker
from refunds_ai_api.services.database import (
    DatabaseConnectionError,
    DatabaseHealth,
    SupabaseDatabaseHealthChecker,
)


class StubDatabaseHealthChecker:
    def __init__(
        self,
        result: DatabaseHealth | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error

    def check(self) -> DatabaseHealth:
        if self._error:
            raise self._error
        if self._result is None:
            raise AssertionError("StubDatabaseHealthChecker requires a result or error.")
        return self._result


class StubCursor:
    def __init__(self) -> None:
        self.executed_statement: str | None = None

    def __enter__(self) -> "StubCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.executed_statement = statement

    def fetchone(self) -> dict[str, int]:
        return {"ok": 1}


class StubConnection:
    def __init__(self, cursor: StubCursor) -> None:
        self.cursor_instance = cursor

    def __enter__(self) -> "StubConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def cursor(self) -> StubCursor:
        return self.cursor_instance


def test_database_health_endpoint_returns_success() -> None:
    app = create_app()
    app.dependency_overrides[get_database_health_checker] = lambda: StubDatabaseHealthChecker(
        DatabaseHealth(
            configured=True,
            connected=True,
            provider="supabase-postgres",
            detail="Database handshake succeeded.",
        )
    )

    response = TestClient(app).get("/health/database")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "provider": "supabase-postgres",
        "configured": True,
        "connected": True,
    }
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_database_health_endpoint_reports_missing_configuration() -> None:
    app = create_app()
    app.dependency_overrides[get_database_health_checker] = lambda: StubDatabaseHealthChecker(
        DatabaseHealth(
            configured=False,
            connected=False,
            provider="supabase-postgres",
            detail="SUPABASE_DB_URL is not configured.",
        )
    )

    response = TestClient(app).get("/health/database")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"] == {
        "provider": "supabase-postgres",
        "configured": False,
        "connected": False,
    }
    assert body["error"] == {
        "code": "DATABASE_NOT_CONFIGURED",
        "message": "SUPABASE_DB_URL is not configured.",
    }


def test_database_health_endpoint_reports_handshake_failure() -> None:
    app = create_app()
    app.dependency_overrides[get_database_health_checker] = lambda: StubDatabaseHealthChecker(
        error=DatabaseConnectionError("Database handshake failed.")
    )

    response = TestClient(app).get("/health/database")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == {
        "code": "DATABASE_CONNECTION_FAILED",
        "message": "Database handshake failed.",
    }


def test_supabase_database_health_checker_reports_missing_url() -> None:
    checker = SupabaseDatabaseHealthChecker(
        Settings(SUPABASE_DB_URL=None, DATABASE_CONNECT_TIMEOUT_SECONDS=5)
    )

    result = checker.check()

    assert result == DatabaseHealth(
        configured=False,
        connected=False,
        provider="supabase-postgres",
        detail="SUPABASE_DB_URL is not configured.",
    )


def test_supabase_database_health_checker_connects_with_configured_url(monkeypatch) -> None:
    cursor = StubCursor()
    calls = []

    def connect(*args, **kwargs):
        calls.append((args, kwargs))
        return StubConnection(cursor)

    monkeypatch.setattr("refunds_ai_api.services.database.psycopg.connect", connect)
    checker = SupabaseDatabaseHealthChecker(
        Settings(
            SUPABASE_DB_URL="postgresql://user:password@example.supabase.co:5432/postgres",
            DATABASE_CONNECT_TIMEOUT_SECONDS=7,
        )
    )

    result = checker.check()

    assert result == DatabaseHealth(
        configured=True,
        connected=True,
        provider="supabase-postgres",
        detail="Database handshake succeeded.",
    )
    assert cursor.executed_statement == "select 1 as ok"
    assert calls[0][0] == ("postgresql://user:password@example.supabase.co:5432/postgres",)
    assert calls[0][1]["connect_timeout"] == 7


def test_supabase_database_health_checker_wraps_operational_errors(monkeypatch) -> None:
    def raise_operational_error(*args, **kwargs):
        raise OperationalError("network unavailable")

    monkeypatch.setattr("refunds_ai_api.services.database.psycopg.connect", raise_operational_error)
    checker = SupabaseDatabaseHealthChecker(
        Settings(
            SUPABASE_DB_URL="postgresql://user:password@example.supabase.co:5432/postgres",
            DATABASE_CONNECT_TIMEOUT_SECONDS=5,
        )
    )

    with pytest.raises(DatabaseConnectionError, match="Database handshake failed."):
        checker.check()


def test_analyze_connection_error_types() -> None:
    from refunds_ai_api.services.database import analyze_connection_error

    # 1. Password fail
    msg = analyze_connection_error(Exception("FATAL: password authentication failed for user test"))
    assert "Invalid credentials" in msg
    assert "password authentication failed" in msg

    # 2. Malformed URI
    msg = analyze_connection_error(Exception("bad connection info parameter: missing '='"))
    assert "Malformed SUPABASE_DB_URL" in msg
    assert "bad connection info" in msg

    # 3. DNS resolution failed
    msg = analyze_connection_error(Exception("could not translate host name 'foo' to address"))
    assert "DNS resolution failed" in msg
    assert "could not translate host" in msg

    # 4. Connection refused
    msg = analyze_connection_error(Exception("connection refused by port 5432"))
    assert "Connection refused" in msg
    assert "connection refused" in msg

    # 5. Connection slots/rate limited
    msg = analyze_connection_error(
        Exception(
            "FATAL: remaining connection slots are reserved for "
            "non-replication superuser connections"
        )
    )
    assert "Supabase connection limit exceeded" in msg

    # 6. Timeout
    msg = analyze_connection_error(Exception("connection timed out"))
    assert "Connection attempt timed out" in msg

    # 7. Fallback
    msg = analyze_connection_error(Exception("some random error"))
    assert "An unexpected database connection error occurred" in msg

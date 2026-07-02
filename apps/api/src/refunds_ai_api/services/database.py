from dataclasses import dataclass
from typing import Protocol

import psycopg
from psycopg import OperationalError
from psycopg.rows import dict_row

from refunds_ai_api.config import Settings


class DatabaseConnectionError(RuntimeError):
    """Raised when the backend cannot complete the database handshake."""


def analyze_connection_error(exc: Exception) -> str:
    """Analyze the connection exception to provide developer-friendly diagnostic details."""
    error_msg = str(exc).strip()
    error_msg_lower = error_msg.lower()

    if "password authentication failed" in error_msg_lower:
        reason = "Invalid credentials. The password or username in SUPABASE_DB_URL is incorrect."
    elif "connection refused" in error_msg_lower:
        reason = (
            "Connection refused by the host. "
            "Ensure the database service is running and accessible on that port."
        )
    elif (
        "could not translate host name" in error_msg_lower
        or "name or service not known" in error_msg_lower
    ):
        reason = (
            "DNS resolution failed. "
            "The hostname in SUPABASE_DB_URL is invalid, or you are offline."
        )
    elif (
        "slots are reserved" in error_msg_lower
        or "too many connections" in error_msg_lower
        or "connection limit exceeded" in error_msg_lower
        or "rate limit" in error_msg_lower
    ):
        reason = (
            "Supabase connection limit exceeded "
            "(rate limited / too many active client connections)."
        )
    elif "timeout" in error_msg_lower or "timed out" in error_msg_lower:
        reason = "Connection attempt timed out. Check your network or firewall rules."
    elif (
        "bad connection info" in error_msg_lower
        or "missing" in error_msg_lower
        or "port" in error_msg_lower
        or "invalid" in error_msg_lower
        or "uri" in error_msg_lower
    ):
        reason = (
            "Malformed SUPABASE_DB_URL connection string. "
            "Check for syntax issues (e.g., missing colons, invalid characters, "
            "or incorrect formatting)."
        )
    else:
        reason = "An unexpected database connection error occurred."

    return (
        f"Database handshake failed. Reason: {reason} "
        f"Detailed error: {error_msg}"
    )


@dataclass(frozen=True)
class DatabaseHealth:
    """Database health-check result safe for API responses."""

    configured: bool
    connected: bool
    provider: str
    detail: str


class DatabaseHealthChecker(Protocol):
    """Protocol for database health-check implementations."""

    def check(self) -> DatabaseHealth:
        """Return current database connectivity state."""
        ...


class SupabaseDatabaseHealthChecker:
    """Validate Supabase PostgreSQL connectivity without touching application schema."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def check(self) -> DatabaseHealth:
        if not self._settings.supabase_db_url:
            return DatabaseHealth(
                configured=False,
                connected=False,
                provider="supabase-postgres",
                detail="SUPABASE_DB_URL is not configured.",
            )

        try:
            with psycopg.connect(
                self._settings.supabase_db_url,
                connect_timeout=self._settings.database_connect_timeout_seconds,
                row_factory=dict_row,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("select 1 as ok")
                    row = cursor.fetchone()
        except OperationalError as exc:
            detailed_msg = analyze_connection_error(exc)
            raise DatabaseConnectionError(detailed_msg) from exc

        if row != {"ok": 1}:
            raise DatabaseConnectionError("Database handshake returned an unexpected result.")

        return DatabaseHealth(
            configured=True,
            connected=True,
            provider="supabase-postgres",
            detail="Database handshake succeeded.",
        )

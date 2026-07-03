"""Idempotent seed-data entry point.

Business seed functions should be added here after the corresponding schema
migrations exist. This module intentionally starts empty so the CLI can expose a
stable seed command before business tables are introduced.
"""

from psycopg import Connection


def seed(connection: Connection) -> list[str]:
    """Run all configured seed steps and return their names."""
    _ = connection
    return []

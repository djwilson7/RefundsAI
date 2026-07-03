"""Idempotent seed-data entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg import Connection

IDENTITY_SEED_FILE = Path(__file__).resolve().parents[3] / "mockdata" / "identity_seed.json"


class SeedDataError(RuntimeError):
    """Raised when configured seed data is structurally invalid."""


def seed(connection: Connection) -> list[str]:
    """Run all configured seed steps and return their names."""
    seed_identity(connection)
    return ["identity"]


def load_identity_seed_data(seed_file: Path = IDENTITY_SEED_FILE) -> dict[str, Any]:
    """Load the identity seed fixture from disk."""
    return json.loads(seed_file.read_text(encoding="utf-8"))


def seed_identity(connection: Connection) -> None:
    """Seed roles, users, and user role assignments."""
    seed_data = load_identity_seed_data()
    validate_identity_seed_data(seed_data)
    roles_by_key = {role["key"]: role for role in seed_data["roles"]}

    with connection.cursor() as cursor:
        for role in seed_data["roles"]:
            cursor.execute(
                """
                insert into public.roles (id, key, name)
                values (%s, %s, %s)
                on conflict (key) do update
                set name = excluded.name
                """,
                (role["id"], role["key"], role["name"]),
            )

        for user in seed_data["users"]:
            cursor.execute(
                """
                insert into public.users (id, first_name, last_name, created_at)
                values (%s, %s, %s, %s)
                on conflict (id) do update
                set first_name = excluded.first_name,
                    last_name = excluded.last_name
                """,
                (user["id"], user["first_name"], user["last_name"], user["created_at"]),
            )

        for user_role in seed_data["user_roles"]:
            cursor.execute(
                """
                insert into public.user_roles (user_id, role_id, created_at)
                values (%s, %s, %s)
                on conflict (user_id, role_id) do nothing
                """,
                (
                    user_role["user_id"],
                    roles_by_key[user_role["role_key"]]["id"],
                    user_role["created_at"],
                ),
            )


def validate_identity_seed_data(seed_data: dict[str, Any]) -> None:
    """Validate the identity seed fixture matches the documented v1 shape."""
    roles = seed_data.get("roles", [])
    users = seed_data.get("users", [])
    user_roles = seed_data.get("user_roles", [])
    role_keys = {role.get("key") for role in roles}
    user_ids = {user.get("id") for user in users}
    customer_assignments = [
        user_role for user_role in user_roles if user_role.get("role_key") == "customer"
    ]
    admin_assignments = [
        user_role for user_role in user_roles if user_role.get("role_key") == "admin"
    ]

    if role_keys != {"customer", "admin"}:
        raise SeedDataError("Identity seed data must define customer and admin roles.")
    if len(users) != 16:
        raise SeedDataError("Identity seed data must define exactly 16 users.")
    if len(user_roles) != 16:
        raise SeedDataError("Identity seed data must define exactly 16 role assignments.")
    if len(customer_assignments) != 15 or len(admin_assignments) != 1:
        raise SeedDataError("Identity seed data must assign 15 customers and 1 admin.")
    if any(user_role.get("user_id") not in user_ids for user_role in user_roles):
        raise SeedDataError("Identity seed data contains a role assignment for an unknown user.")
    if any(user_role.get("role_key") not in role_keys for user_role in user_roles):
        raise SeedDataError("Identity seed data contains an unknown role key.")

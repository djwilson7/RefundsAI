"""Idempotent seed-data entry point."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from psycopg import Connection

IDENTITY_SEED_FILE = Path(__file__).resolve().parents[3] / "mockdata" / "identity_seed.json"
PURCHASE_SEED_FILE = Path(__file__).resolve().parents[3] / "mockdata" / "purchase_seed.json"
PURCHASE_DETAIL_SEED_NOW = datetime(2026, 7, 3, 23, 59, 59, tzinfo=UTC)


class SeedDataError(RuntimeError):
    """Raised when configured seed data is structurally invalid."""


def seed(connection: Connection) -> list[str]:
    """Run all configured seed steps and return their names."""
    seed_identity(connection)
    seed_purchase_catalog(connection)
    seed_purchase_details(connection)
    return ["identity", "purchase_catalog", "purchase_details"]


def load_identity_seed_data(seed_file: Path = IDENTITY_SEED_FILE) -> dict[str, Any]:
    """Load the identity seed fixture from disk."""
    return json.loads(seed_file.read_text(encoding="utf-8"))


def load_purchase_seed_data(seed_file: Path = PURCHASE_SEED_FILE) -> dict[str, Any]:
    """Load the purchase catalog seed fixture from disk."""
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


def seed_purchase_catalog(connection: Connection) -> None:
    """Seed products and deterministic customer purchase history."""
    seed_data = load_purchase_seed_data()
    identity_seed_data = load_identity_seed_data()
    validate_purchase_seed_data(seed_data)
    purchases = build_purchase_seed_rows(seed_data, identity_seed_data)

    with connection.cursor() as cursor:
        for product in seed_data["products"]:
            cursor.execute(
                """
                insert into public.products (
                    id,
                    name,
                    sku,
                    product_type,
                    base_price_cents
                )
                values (%s, %s, %s, %s, %s)
                on conflict (sku) do update
                set name = excluded.name,
                    product_type = excluded.product_type,
                    base_price_cents = excluded.base_price_cents,
                    updated_at = now()
                """,
                (
                    product["id"],
                    product["name"],
                    product["sku"],
                    product["product_type"],
                    product["base_price_cents"],
                ),
            )

        for purchase in purchases:
            cursor.execute(
                """
                insert into public.purchases (
                    id,
                    user_id,
                    product_id,
                    order_number,
                    purchase_type,
                    amount_cents,
                    purchased_at,
                    status
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (order_number) do update
                set user_id = excluded.user_id,
                    product_id = excluded.product_id,
                    purchase_type = excluded.purchase_type,
                    amount_cents = excluded.amount_cents,
                    purchased_at = excluded.purchased_at,
                    status = excluded.status,
                    updated_at = now()
                """,
                (
                    purchase["id"],
                    purchase["user_id"],
                    purchase["product_id"],
                    purchase["order_number"],
                    purchase["purchase_type"],
                    purchase["amount_cents"],
                    purchase["purchased_at"],
                    purchase["status"],
                ),
            )


def seed_purchase_details(connection: Connection) -> None:
    """Seed deterministic lifecycle detail rows for every purchase."""
    purchase_seed_data = load_purchase_seed_data()
    identity_seed_data = load_identity_seed_data()
    validate_purchase_seed_data(purchase_seed_data)
    purchases = build_purchase_seed_rows(purchase_seed_data, identity_seed_data)
    detail_rows = build_purchase_detail_seed_rows(purchases)
    validate_purchase_detail_seed_rows(purchases, detail_rows)

    with connection.cursor() as cursor:
        for detail in detail_rows["digital"]:
            cursor.execute(
                """
                insert into public.digital_purchase_details (
                    id,
                    purchase_id,
                    issued_code,
                    code_redeemed,
                    code_redeemed_at,
                    code_invalidated_at
                )
                values (%s, %s, %s, %s, %s, %s)
                on conflict (purchase_id) do update
                set issued_code = excluded.issued_code,
                    code_redeemed = excluded.code_redeemed,
                    code_redeemed_at = excluded.code_redeemed_at,
                    code_invalidated_at = excluded.code_invalidated_at,
                    updated_at = now()
                """,
                (
                    detail["id"],
                    detail["purchase_id"],
                    detail["issued_code"],
                    detail["code_redeemed"],
                    detail["code_redeemed_at"],
                    detail["code_invalidated_at"],
                ),
            )

        for detail in detail_rows["physical"]:
            cursor.execute(
                """
                insert into public.physical_purchase_details (
                    id,
                    purchase_id,
                    scheduled_delivery_at,
                    delivered_at,
                    return_status,
                    carrier,
                    tracking_number
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (purchase_id) do update
                set scheduled_delivery_at = excluded.scheduled_delivery_at,
                    delivered_at = excluded.delivered_at,
                    return_status = excluded.return_status,
                    carrier = excluded.carrier,
                    tracking_number = excluded.tracking_number,
                    updated_at = now()
                """,
                (
                    detail["id"],
                    detail["purchase_id"],
                    detail["scheduled_delivery_at"],
                    detail["delivered_at"],
                    detail["return_status"],
                    detail["carrier"],
                    detail["tracking_number"],
                ),
            )

        for detail in detail_rows["subscription"]:
            cursor.execute(
                """
                insert into public.subscription_purchase_details (
                    id,
                    purchase_id,
                    period_start,
                    period_end
                )
                values (%s, %s, %s, %s)
                on conflict (purchase_id) do update
                set period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    updated_at = now()
                """,
                (
                    detail["id"],
                    detail["purchase_id"],
                    detail["period_start"],
                    detail["period_end"],
                ),
            )


def build_purchase_seed_rows(
    purchase_seed_data: dict[str, Any],
    identity_seed_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build deterministic customer purchase rows from the seed plan."""
    customer_user_ids = [
        assignment["user_id"]
        for assignment in identity_seed_data["user_roles"]
        if assignment["role_key"] == "customer"
    ]
    products_by_type = {
        product_type: [
            product
            for product in purchase_seed_data["products"]
            if product["product_type"] == product_type
        ]
        for product_type in ("physical", "digital", "subscription")
    }
    plan = purchase_seed_data["purchase_plan"]
    type_sequence = build_purchase_type_sequence(plan["type_distribution"])
    first_order_number = plan["first_order_number"]
    first_purchase_at = datetime.fromisoformat(
        plan["first_purchase_at"].replace("Z", "+00:00")
    )
    active_day_window = (
        datetime.fromisoformat(plan["last_purchase_at"].replace("Z", "+00:00"))
        - first_purchase_at
    ).days + 1
    purchases: list[dict[str, Any]] = []

    for customer_index, user_id in enumerate(customer_user_ids):
        for purchase_index in range(plan["purchases_per_customer"]):
            sequence_index = customer_index * plan["purchases_per_customer"] + purchase_index
            product_type = type_sequence[sequence_index]
            product_options = products_by_type[product_type]
            product = product_options[(customer_index + purchase_index) % len(product_options)]
            purchased_at = first_purchase_at + timedelta(
                days=sequence_index % active_day_window,
                minutes=sequence_index,
            )

            purchases.append(
                {
                    "id": (
                        "40000000-0000-4000-8000-"
                        f"{sequence_index + 1:012d}"
                    ),
                    "user_id": user_id,
                    "product_id": product["id"],
                    "order_number": f"RAI-{first_order_number + sequence_index}",
                    "purchase_type": product["product_type"],
                    "amount_cents": product["base_price_cents"],
                    "purchased_at": purchased_at.astimezone(UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "status": plan["status"],
                }
            )

    return purchases


def build_purchase_detail_seed_rows(
    purchases: list[dict[str, Any]],
    seed_now: datetime = PURCHASE_DETAIL_SEED_NOW,
) -> dict[str, list[dict[str, Any]]]:
    """Build one deterministic product-lifecycle detail row per purchase."""
    detail_rows: dict[str, list[dict[str, Any]]] = {
        "digital": [],
        "physical": [],
        "subscription": [],
    }
    carriers = ("UPS", "FedEx", "USPS", "DHL")

    for purchase in purchases:
        purchased_at = parse_seed_datetime(purchase["purchased_at"])

        if purchase["purchase_type"] == "digital":
            digital_index = len(detail_rows["digital"])
            code_redeemed = digital_index % 4 == 0
            code_redeemed_at = (
                format_seed_datetime(purchased_at + timedelta(hours=1))
                if code_redeemed
                else None
            )
            detail_rows["digital"].append(
                {
                    "id": f"50000000-0000-4000-8000-{digital_index + 1:012d}",
                    "purchase_id": purchase["id"],
                    "issued_code": f"DIG-{purchase['order_number']}",
                    "code_redeemed": code_redeemed,
                    "code_redeemed_at": code_redeemed_at,
                    "code_invalidated_at": None,
                }
            )
            continue

        if purchase["purchase_type"] == "physical":
            physical_index = len(detail_rows["physical"])
            scheduled_delivery_at = purchased_at + timedelta(days=2 + (physical_index % 6))
            delivered_at = scheduled_delivery_at if scheduled_delivery_at <= seed_now else None
            detail_rows["physical"].append(
                {
                    "id": f"60000000-0000-4000-8000-{physical_index + 1:012d}",
                    "purchase_id": purchase["id"],
                    "scheduled_delivery_at": format_seed_datetime(scheduled_delivery_at),
                    "delivered_at": (
                        format_seed_datetime(delivered_at)
                        if delivered_at is not None
                        else None
                    ),
                    "return_status": "not_requested",
                    "carrier": carriers[physical_index % len(carriers)],
                    "tracking_number": f"TRK-{purchase['order_number']}",
                }
            )
            continue

        if purchase["purchase_type"] == "subscription":
            subscription_index = len(detail_rows["subscription"])
            detail_rows["subscription"].append(
                {
                    "id": f"70000000-0000-4000-8000-{subscription_index + 1:012d}",
                    "purchase_id": purchase["id"],
                    "period_start": format_seed_datetime(purchased_at),
                    "period_end": format_seed_datetime(purchased_at + timedelta(days=30)),
                }
            )

    return detail_rows


def build_purchase_type_sequence(type_distribution: dict[str, int]) -> list[str]:
    """Build a deterministic purchase type sequence from target distribution counts."""
    purchase_types = (
        ["physical"] * type_distribution["physical"]
        + ["digital"] * type_distribution["digital"]
        + ["subscription"] * type_distribution["subscription"]
    )
    customer_count = 15
    purchases_per_customer = 12

    return [
        purchase_types[customer_index + (purchase_index * customer_count)]
        for customer_index in range(customer_count)
        for purchase_index in range(purchases_per_customer)
    ]


def parse_seed_datetime(value: str) -> datetime:
    """Parse a UTC ISO seed timestamp."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_seed_datetime(value: datetime) -> str:
    """Format a seed timestamp as a stable UTC ISO value."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def validate_purchase_seed_data(seed_data: dict[str, Any]) -> None:
    """Validate the purchase seed fixture matches the documented v1 shape."""
    products = seed_data.get("products", [])
    purchase_plan = seed_data.get("purchase_plan", {})
    product_types = [product.get("product_type") for product in products]

    if len(products) != 30:
        raise SeedDataError("Purchase seed data must define exactly 30 products.")
    if product_types.count("physical") != 14:
        raise SeedDataError("Purchase seed data must define exactly 14 physical products.")
    if product_types.count("digital") != 10:
        raise SeedDataError("Purchase seed data must define exactly 10 digital products.")
    if product_types.count("subscription") != 6:
        raise SeedDataError("Purchase seed data must define exactly 6 subscription products.")
    if len({product.get("sku") for product in products}) != len(products):
        raise SeedDataError("Purchase seed data product SKUs must be unique.")
    if any(product.get("base_price_cents", -1) < 0 for product in products):
        raise SeedDataError("Purchase seed data product prices must be non-negative.")
    if purchase_plan.get("customer_count") != 15:
        raise SeedDataError("Purchase seed plan must target exactly 15 customers.")
    if purchase_plan.get("purchases_per_customer") != 12:
        raise SeedDataError("Purchase seed plan must create 12 purchases per customer.")
    if purchase_plan.get("status") != "completed":
        raise SeedDataError("Purchase seed plan must keep all purchases active.")
    type_distribution = purchase_plan.get("type_distribution", {})
    expected_purchase_count = (
        purchase_plan.get("customer_count", 0)
        * purchase_plan.get("purchases_per_customer", 0)
    )
    if sum(type_distribution.values()) != expected_purchase_count:
        raise SeedDataError("Purchase seed plan distribution must match total purchases.")
    if type_distribution != {"physical": 90, "digital": 54, "subscription": 36}:
        raise SeedDataError("Purchase seed plan must distribute purchases 90/54/36 by type.")
    first_purchase_at = datetime.fromisoformat(
        purchase_plan["first_purchase_at"].replace("Z", "+00:00")
    )
    last_purchase_at = datetime.fromisoformat(
        purchase_plan["last_purchase_at"].replace("Z", "+00:00")
    )
    if (last_purchase_at - first_purchase_at).days != 44:
        raise SeedDataError("Purchase seed plan must span the last 45 days.")


def validate_purchase_detail_seed_rows(
    purchases: list[dict[str, Any]],
    detail_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Validate product-lifecycle detail rows match their owning purchase types."""
    purchase_ids_by_type = {
        purchase_type: {
            purchase["id"]
            for purchase in purchases
            if purchase["purchase_type"] == purchase_type
        }
        for purchase_type in ("digital", "physical", "subscription")
    }
    detail_purchase_ids_by_type = {
        purchase_type: {row["purchase_id"] for row in detail_rows[purchase_type]}
        for purchase_type in ("digital", "physical", "subscription")
    }

    for purchase_type in ("digital", "physical", "subscription"):
        if detail_purchase_ids_by_type[purchase_type] != purchase_ids_by_type[purchase_type]:
            raise SeedDataError(
                f"{purchase_type} detail rows must match {purchase_type} purchases."
            )

    all_detail_purchase_ids = [
        row["purchase_id"]
        for purchase_type in ("digital", "physical", "subscription")
        for row in detail_rows[purchase_type]
    ]
    if len(all_detail_purchase_ids) != len(set(all_detail_purchase_ids)):
        raise SeedDataError("Each purchase must have exactly one matching detail row.")

    issued_codes = [row["issued_code"] for row in detail_rows["digital"]]
    if len(issued_codes) != len(set(issued_codes)):
        raise SeedDataError("Digital issued_code values must be unique.")
    if any(row["code_invalidated_at"] is not None for row in detail_rows["digital"]):
        raise SeedDataError("Digital code_invalidated_at values must remain null.")
    for row in detail_rows["digital"]:
        if row["code_redeemed"] and row["code_redeemed_at"] is None:
            raise SeedDataError("Redeemed digital codes must include code_redeemed_at.")

    purchases_by_id = {purchase["id"]: purchase for purchase in purchases}
    for row in detail_rows["physical"]:
        purchase = purchases_by_id[row["purchase_id"]]
        purchased_at = parse_seed_datetime(purchase["purchased_at"])
        scheduled_delivery_at = parse_seed_datetime(row["scheduled_delivery_at"])
        if scheduled_delivery_at <= purchased_at:
            raise SeedDataError("Physical scheduled_delivery_at must be after purchased_at.")
        if scheduled_delivery_at < purchased_at + timedelta(days=2):
            raise SeedDataError("Physical scheduled_delivery_at must be at least 2 days out.")
        if scheduled_delivery_at > purchased_at + timedelta(days=7):
            raise SeedDataError("Physical scheduled_delivery_at must be at most 7 days out.")
        if row["delivered_at"] is not None:
            delivered_at = parse_seed_datetime(row["delivered_at"])
            if delivered_at > scheduled_delivery_at:
                raise SeedDataError("Physical delivered_at must be on or before delivery.")
        if row["return_status"] != "not_requested":
            raise SeedDataError("Physical return_status must remain not_requested.")

    for row in detail_rows["subscription"]:
        period_start = parse_seed_datetime(row["period_start"])
        period_end = parse_seed_datetime(row["period_end"])
        if period_end <= period_start:
            raise SeedDataError("Subscription period_end must be after period_start.")

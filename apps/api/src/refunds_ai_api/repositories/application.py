"""Repositories for frontend-facing application read and workflow paths."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from refunds_ai_api.config import Settings


class RepositoryConfigurationError(RuntimeError):
    """Raised when repository database access is not configured."""


class EntityNotFoundError(RuntimeError):
    """Raised when a requested application entity does not exist."""


class PurchaseDetailsNotFoundError(RuntimeError):
    """Raised when a purchase has no matching type-specific detail row."""


class RepositoryConflictError(RuntimeError):
    """Raised when a guarded repository mutation cannot apply exactly once."""


class ConnectionProvider(Protocol):
    """Opens backend-owned database connections for repository operations."""

    @contextmanager
    def open(self) -> Iterator[Connection]:
        """Yield an open database connection."""
        ...


@dataclass(frozen=True)
class PsycopgConnectionProvider:
    """Open psycopg connections using backend Supabase configuration."""

    settings: Settings

    @contextmanager
    def open(self) -> Iterator[Connection]:
        """Yield a configured psycopg connection."""
        if not self.settings.supabase_db_url:
            raise RepositoryConfigurationError("SUPABASE_DB_URL is not configured.")

        with psycopg.connect(
            self.settings.supabase_db_url,
            connect_timeout=self.settings.database_connect_timeout_seconds,
            row_factory=dict_row,
        ) as connection:
            yield connection


@dataclass(frozen=True)
class ApplicationRepository:
    """Read frontend-facing identity, purchase, and detail data from PostgreSQL."""

    connection_provider: ConnectionProvider

    def list_mock_users(self) -> list[dict[str, Any]]:
        """Return all seeded mock users with their role assignments."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        users.id,
                        users.first_name,
                        users.last_name,
                        users.created_at,
                        roles.key as role_key,
                        roles.name as role_name
                    from public.users
                    join public.user_roles on user_roles.user_id = users.id
                    join public.roles on roles.id = user_roles.role_id
                    order by users.last_name, users.first_name, roles.key
                    """
                )
                return group_user_role_rows(cursor.fetchall())

    def get_user(self, user_id: str) -> dict[str, Any]:
        """Return one user with role assignments."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        users.id,
                        users.first_name,
                        users.last_name,
                        users.created_at,
                        roles.key as role_key,
                        roles.name as role_name
                    from public.users
                    join public.user_roles on user_roles.user_id = users.id
                    join public.roles on roles.id = user_roles.role_id
                    where users.id = %s
                    order by roles.key
                    """,
                    (user_id,),
                )
                users = group_user_role_rows(cursor.fetchall())

        if not users:
            raise EntityNotFoundError("User was not found.")

        return users[0]

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        """Return purchase history rows for a user."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        purchases.id,
                        purchases.order_number,
                        purchases.purchase_type,
                        products.name as product_name,
                        products.sku,
                        purchases.amount_cents,
                        purchases.purchased_at,
                        purchases.status
                    from public.purchases
                    join public.products on products.id = purchases.product_id
                    where purchases.user_id = %s
                    order by purchases.purchased_at desc
                    """,
                    (user_id,),
                )
                return [dict(row) for row in cursor.fetchall()]

    def update_physical_refund_requested(self, purchase_id: str, requested_at: Any) -> None:
        """Prepare a physical purchase for return shipment."""
        self._run_in_transaction(
            (
                """
                update public.physical_purchase_details
                set return_status = 'requested',
                    return_requested_at = %s,
                    return_barcode_generated = true,
                    return_label_created_at = %s,
                    updated_at = now()
                where purchase_id = %s
                    and return_status = 'not_requested'
                    and return_requested_at is null
                    and return_label_created_at is null
                    and return_barcode_generated = false
                    and exists (
                        select 1
                        from public.purchases
                        where purchases.id = physical_purchase_details.purchase_id
                            and purchases.purchase_type = 'physical'
                            and purchases.status = 'completed'
                    )
                """,
                (requested_at, requested_at, purchase_id),
            ),
            (
                """
                update public.purchases
                set status = 'refund_pending',
                    refund_requested_at = %s,
                    updated_at = now()
                where id = %s
                    and purchase_type = 'physical'
                    and status = 'completed'
                """,
                (requested_at, purchase_id),
            ),
        )

    def update_digital_refund_requested(self, purchase_id: str, requested_at: Any) -> None:
        """Invalidate a digital entitlement before refund issuance."""
        self._run_in_transaction(
            (
                """
                update public.digital_purchase_details
                set code_invalidated_at = %s,
                    updated_at = now()
                where purchase_id = %s
                    and code_redeemed = false
                    and code_invalidated_at is null
                    and exists (
                        select 1
                        from public.purchases
                        where purchases.id = digital_purchase_details.purchase_id
                            and purchases.purchase_type = 'digital'
                            and purchases.status = 'completed'
                    )
                """,
                (requested_at, purchase_id),
            ),
            (
                """
                update public.purchases
                set status = 'refund_pending',
                    refund_requested_at = %s,
                    updated_at = now()
                where id = %s
                    and purchase_type = 'digital'
                    and status = 'completed'
                """,
                (requested_at, purchase_id),
            ),
        )

    def update_subscription_refund_requested(
        self,
        purchase_id: str,
        requested_at: Any,
        refund_proration_mode: str,
    ) -> None:
        """Cancel a subscription before refund issuance."""
        self._run_in_transaction(
            (
                """
                update public.subscription_purchase_details
                set cancelled_at = %s,
                    service_ended_at = %s,
                    auto_renew = false,
                    refund_proration_mode = %s,
                    updated_at = now()
                where purchase_id = %s
                    and cancelled_at is null
                    and service_ended_at is null
                    and auto_renew = true
                    and refund_proration_mode = 'none'
                    and exists (
                        select 1
                        from public.purchases
                        where purchases.id = subscription_purchase_details.purchase_id
                            and purchases.purchase_type = 'subscription'
                            and purchases.status in ('completed', 'subscribed')
                    )
                """,
                (requested_at, requested_at, refund_proration_mode, purchase_id),
            ),
            (
                """
                update public.purchases
                set status = 'refund_pending',
                    refund_requested_at = %s,
                    updated_at = now()
                where id = %s
                    and purchase_type = 'subscription'
                    and status in ('completed', 'subscribed')
                """,
                (requested_at, purchase_id),
            ),
        )

    def update_refund_issued(
        self,
        purchase_id: str,
        issued_at: Any,
        refund_amount_cents: int,
        refund_outcome: str,
    ) -> None:
        """Mark a prepared refund as mock-issued."""
        self._run_in_transaction(
            (
                """
                update public.purchases
                set status = 'refunded',
                    refunded_at = %s,
                    refund_amount_cents = %s,
                    refund_outcome = %s,
                    updated_at = now()
                where id = %s
                    and status = 'refund_pending'
                """,
                (issued_at, refund_amount_cents, refund_outcome, purchase_id),
            )
        )

    def update_digital_code_redeemed(self, purchase_id: str, redeemed_at: Any) -> None:
        """Redeem an issued digital code."""
        self._run_in_transaction(
            (
                """
                update public.digital_purchase_details
                set code_redeemed = true,
                    code_redeemed_at = %s,
                    updated_at = now()
                where purchase_id = %s
                    and code_redeemed = false
                    and code_invalidated_at is null
                    and exists (
                        select 1
                        from public.purchases
                        where purchases.id = digital_purchase_details.purchase_id
                            and purchases.purchase_type = 'digital'
                            and purchases.status = 'completed'
                    )
                """,
                (redeemed_at, purchase_id),
            ),
            (
                """
                update public.purchases
                set status = 'redeemed',
                    updated_at = now()
                where id = %s
                    and purchase_type = 'digital'
                    and status = 'completed'
                """,
                (purchase_id,),
            ),
        )

    def update_physical_carrier_acceptance(self, purchase_id: str, accepted_at: Any) -> None:
        """Confirm that a physical return package was accepted by the carrier."""
        self._run_in_transaction(
            (
                """
                update public.physical_purchase_details
                set return_status = 'accepted_by_carrier',
                    accepted_by_carrier_at = %s,
                    updated_at = now()
                where purchase_id = %s
                    and return_status = 'requested'
                    and return_barcode_generated = true
                    and return_requested_at is not null
                    and accepted_by_carrier_at is null
                    and exists (
                        select 1
                        from public.purchases
                        where purchases.id = physical_purchase_details.purchase_id
                            and purchases.purchase_type = 'physical'
                            and purchases.status = 'refund_pending'
                    )
                """,
                (accepted_at, purchase_id),
            )
        )

    def get_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        """Return the matching type-specific detail row for a purchase."""
        purchase = self._get_purchase_type(purchase_id)
        purchase_type = purchase["purchase_type"]

        if purchase_type == "digital":
            details = self._get_digital_purchase_detail(purchase_id)
        elif purchase_type == "physical":
            details = self._get_physical_purchase_detail(purchase_id)
        elif purchase_type == "subscription":
            details = self._get_subscription_purchase_detail(purchase_id)
        else:
            raise PurchaseDetailsNotFoundError(
                f"Unsupported purchase type for detail lookup: {purchase_type}."
            )

        return {
            "purchase_id": purchase["id"],
            "purchase_type": purchase_type,
            "details": details,
        }

    def _get_purchase_type(self, purchase_id: str) -> dict[str, Any]:
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select id, purchase_type
                    from public.purchases
                    where id = %s
                    """,
                    (purchase_id,),
                )
                row = cursor.fetchone()

        if row is None:
            raise EntityNotFoundError("Purchase was not found.")

        return dict(row)

    def get_purchase_for_refund_policy(self, purchase_id: str) -> dict[str, Any]:
        """Return purchase and matching detail facts required for refund policy."""
        purchase = self._get_purchase_for_refund_policy(purchase_id)
        purchase_detail = self.get_purchase_detail(purchase_id)

        return {
            "purchase": purchase,
            "detail": purchase_detail["details"],
        }

    def _get_purchase_for_refund_policy(self, purchase_id: str) -> dict[str, Any]:
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        id,
                        purchase_type,
                        amount_cents,
                        purchased_at,
                        status,
                        refund_requested_at,
                        refunded_at,
                        refund_amount_cents,
                        refund_outcome
                    from public.purchases
                    where id = %s
                    """,
                    (purchase_id,),
                )
                row = cursor.fetchone()

        if row is None:
            raise EntityNotFoundError("Purchase was not found.")

        return dict(row)

    def _get_digital_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        return self._get_single_detail_row(
            """
            select
                issued_code,
                code_redeemed,
                code_redeemed_at,
                code_invalidated_at,
                code_delivered_at,
                refund_window_expires_at,
                refund_lock_reason
            from public.digital_purchase_details
            where purchase_id = %s
            """,
            purchase_id,
        )

    def _get_physical_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        return self._get_single_detail_row(
            """
            select
                scheduled_delivery_at,
                delivered_at,
                return_status,
                carrier,
                tracking_number,
                return_barcode_generated,
                return_label_created_at,
                accepted_by_carrier_at,
                return_requested_at,
                return_authorized_at,
                return_received_at,
                return_rejected_at,
                return_rejection_reason,
                refund_window_expires_at
            from public.physical_purchase_details
            where purchase_id = %s
            """,
            purchase_id,
        )

    def _get_subscription_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        return self._get_single_detail_row(
            """
            select
                period_start,
                period_end,
                cancelled_at,
                service_ended_at,
                auto_renew,
                refund_proration_mode,
                full_refund_window_expires_at,
                refund_window_expires_at
            from public.subscription_purchase_details
            where purchase_id = %s
            """,
            purchase_id,
        )

    def _get_single_detail_row(self, statement: str, purchase_id: str) -> dict[str, Any]:
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, (purchase_id,))
                row = cursor.fetchone()

        if row is None:
            raise PurchaseDetailsNotFoundError("Purchase detail row was not found.")

        return dict(row)

    def _run_in_transaction(self, *statements: tuple[str, tuple[Any, ...]]) -> None:
        with self.connection_provider.open() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    for statement, params in statements:
                        cursor.execute(statement, params)
                        if cursor.rowcount != 1:
                            raise RepositoryConflictError(
                                "Guarded repository mutation did not match expected state."
                            )


def group_user_role_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group one-row-per-role SQL results into one user payload per user."""
    users_by_id: dict[str, dict[str, Any]] = {}

    for row in rows:
        user_id = str(row["id"])
        user = users_by_id.setdefault(
            user_id,
            {
                "id": row["id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "created_at": row["created_at"],
                "display_name": f"{row['first_name']} {row['last_name']}",
                "roles": [],
            },
        )
        user["roles"].append(
            {
                "key": row["role_key"],
                "name": row["role_name"],
            }
        )

    return list(users_by_id.values())

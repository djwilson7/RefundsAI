"""Frontend-facing application API endpoints for users, purchases, and refunds."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from refunds_ai_api.config import get_settings
from refunds_ai_api.repositories.application import (
    ApplicationRepository,
    EntityNotFoundError,
    PsycopgConnectionProvider,
    PurchaseDetailsNotFoundError,
    RepositoryConfigurationError,
)
from refunds_ai_api.schemas.application import (
    PurchaseDetailsRead,
    PurchaseSummaryRead,
    RefundEligibilityRead,
    UserRead,
)
from refunds_ai_api.schemas.responses import ApiResponse
from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.refund_policy import RefundWorkflowError

router = APIRouter(prefix="/api", tags=["application"])


def response_meta() -> dict[str, str]:
    """Return standard response metadata."""
    return {"timestamp": datetime.now(UTC).isoformat()}


def get_application_service() -> ApplicationService:
    """Build the frontend application service from backend database settings."""
    connection_provider = PsycopgConnectionProvider(get_settings())
    repository = ApplicationRepository(connection_provider)
    return ApplicationService(repository)


@router.get("/users/mock", response_model=ApiResponse)
def list_mock_users(
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Return selectable mock users for the frontend login flow."""
    try:
        users = [
            UserRead.model_validate(user).model_dump(mode="json")
            for user in service.list_mock_users()
        ]
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(success=True, data={"users": users}, error=None, meta=response_meta())


@router.get("/users/{user_id}", response_model=ApiResponse)
def get_user(
    user_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Return one selected mock user with role information."""
    try:
        user = UserRead.model_validate(service.get_user(str(user_id))).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "USER_NOT_FOUND", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(success=True, data={"user": user}, error=None, meta=response_meta())


@router.get("/users/{user_id}/purchases", response_model=ApiResponse)
def list_user_purchases(
    user_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Return purchase history for one selected user."""
    try:
        purchases = [
            PurchaseSummaryRead.model_validate(purchase).model_dump(mode="json")
            for purchase in service.list_user_purchases(str(user_id))
        ]
    except EntityNotFoundError as exc:
        return not_found_response(response, "USER_NOT_FOUND", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(
        success=True,
        data={"purchases": purchases},
        error=None,
        meta=response_meta(),
    )


@router.get("/purchases/{purchase_id}/details", response_model=ApiResponse)
def get_purchase_details(
    purchase_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Return type-specific purchase details resolved by the backend."""
    try:
        purchase_details = PurchaseDetailsRead.model_validate(
            service.get_purchase_detail(str(purchase_id))
        ).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "PURCHASE_NOT_FOUND", str(exc))
    except PurchaseDetailsNotFoundError as exc:
        return not_found_response(response, "PURCHASE_DETAILS_NOT_FOUND", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(
        success=True,
        data=purchase_details,
        error=None,
        meta=response_meta(),
    )


@router.get("/purchases/{purchase_id}/refund/eligibility", response_model=ApiResponse)
def get_refund_eligibility(
    purchase_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Return deterministic refund eligibility for one purchase."""
    try:
        eligibility = RefundEligibilityRead.model_validate(
            service.get_refund_workflow(str(purchase_id))
        ).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "PURCHASE_NOT_FOUND", str(exc))
    except PurchaseDetailsNotFoundError as exc:
        return not_found_response(response, "PURCHASE_DETAILS_NOT_FOUND", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(
        success=True,
        data=eligibility,
        error=None,
        meta=response_meta(),
    )


@router.post("/purchases/{purchase_id}/refund/request", response_model=ApiResponse)
def request_refund(
    purchase_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Prepare a purchase for refund without issuing funds."""
    try:
        workflow = RefundEligibilityRead.model_validate(
            service.request_refund(str(purchase_id))
        ).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "PURCHASE_NOT_FOUND", str(exc))
    except PurchaseDetailsNotFoundError as exc:
        return not_found_response(response, "PURCHASE_DETAILS_NOT_FOUND", str(exc))
    except RefundWorkflowError as exc:
        return workflow_error_response(response, "REFUND_PREPARATION_NOT_ALLOWED", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(success=True, data=workflow, error=None, meta=response_meta())


@router.post("/purchases/{purchase_id}/refund/issue", response_model=ApiResponse)
def issue_refund(
    purchase_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Issue mock refund funds for a prepared purchase."""
    try:
        workflow = RefundEligibilityRead.model_validate(
            service.issue_refund(str(purchase_id))
        ).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "PURCHASE_NOT_FOUND", str(exc))
    except PurchaseDetailsNotFoundError as exc:
        return not_found_response(response, "PURCHASE_DETAILS_NOT_FOUND", str(exc))
    except RefundWorkflowError as exc:
        return workflow_error_response(response, "REFUND_ISSUANCE_NOT_ALLOWED", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(success=True, data=workflow, error=None, meta=response_meta())


@router.post("/purchases/{purchase_id}/digital/redeem-code", response_model=ApiResponse)
def redeem_digital_code(
    purchase_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Redeem a digital issued code when refund state does not block redemption."""
    try:
        details = PurchaseDetailsRead.model_validate(
            service.redeem_digital_code(str(purchase_id))
        ).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "PURCHASE_NOT_FOUND", str(exc))
    except PurchaseDetailsNotFoundError as exc:
        return not_found_response(response, "PURCHASE_DETAILS_NOT_FOUND", str(exc))
    except RefundWorkflowError as exc:
        return workflow_error_response(response, "CODE_REDEMPTION_NOT_ALLOWED", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(success=True, data=details, error=None, meta=response_meta())


@router.post(
    "/purchases/{purchase_id}/physical/confirm-carrier-acceptance",
    response_model=ApiResponse,
)
def confirm_carrier_acceptance(
    purchase_id: UUID,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    response: Response,
) -> ApiResponse:
    """Confirm that a physical return package was accepted by the carrier."""
    try:
        workflow = RefundEligibilityRead.model_validate(
            service.confirm_carrier_acceptance(str(purchase_id))
        ).model_dump(mode="json")
    except EntityNotFoundError as exc:
        return not_found_response(response, "PURCHASE_NOT_FOUND", str(exc))
    except PurchaseDetailsNotFoundError as exc:
        return not_found_response(response, "PURCHASE_DETAILS_NOT_FOUND", str(exc))
    except RefundWorkflowError as exc:
        return workflow_error_response(
            response,
            "CARRIER_ACCEPTANCE_NOT_ALLOWED",
            str(exc),
        )
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(success=True, data=workflow, error=None, meta=response_meta())


def not_found_response(response: Response, code: str, message: str) -> ApiResponse:
    """Return a standardized not-found API response."""
    response.status_code = status.HTTP_404_NOT_FOUND
    return ApiResponse(
        success=False,
        data=None,
        error={"code": code, "message": message},
        meta=response_meta(),
    )


def service_unavailable_response(response: Response, code: str, message: str) -> ApiResponse:
    """Return a standardized service-unavailable API response."""
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ApiResponse(
        success=False,
        data=None,
        error={"code": code, "message": message},
        meta=response_meta(),
    )


def workflow_error_response(response: Response, code: str, message: str) -> ApiResponse:
    """Return a standardized workflow-denied API response."""
    response.status_code = status.HTTP_409_CONFLICT
    return ApiResponse(
        success=False,
        data=None,
        error={"code": code, "message": message},
        meta=response_meta(),
    )

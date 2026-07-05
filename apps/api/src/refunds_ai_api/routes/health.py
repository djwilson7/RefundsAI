from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from refunds_ai_api.config import get_settings
from refunds_ai_api.schemas.responses import ApiResponse
from refunds_ai_api.services.database import (
    DatabaseConnectionError,
    DatabaseHealthChecker,
    SupabaseDatabaseHealthChecker,
)
from refunds_ai_api.services.model_health import (
    ModelConnectionError,
    ModelHealthChecker,
    OpenAIModelHealthChecker,
)

router = APIRouter(tags=["system"])


def get_database_health_checker() -> DatabaseHealthChecker:
    """Build the database health checker from current backend settings."""
    return SupabaseDatabaseHealthChecker(get_settings())


def get_model_health_checker() -> ModelHealthChecker:
    """Build the OpenAI model health checker from current backend settings."""
    return OpenAIModelHealthChecker(get_settings())


@router.get("/health", response_model=ApiResponse)
def health_check() -> ApiResponse:
    """Return service readiness using the standard API response envelope."""
    return ApiResponse(
        success=True,
        data={
            "service": "refunds-ai-api",
            "status": "ok",
        },
        error=None,
        meta={
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@router.get("/health/database", response_model=ApiResponse)
def database_health_check(
    checker: Annotated[DatabaseHealthChecker, Depends(get_database_health_checker)],
    response: Response,
) -> ApiResponse:
    """Return Supabase PostgreSQL readiness without exposing credentials."""
    try:
        database_health = checker.check()
    except DatabaseConnectionError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(
            success=False,
            data=None,
            error={
                "code": "DATABASE_CONNECTION_FAILED",
                "message": str(exc),
            },
            meta={
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    if not database_health.configured:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(
            success=False,
            data={
                "provider": database_health.provider,
                "configured": database_health.configured,
                "connected": database_health.connected,
            },
            error={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": database_health.detail,
            },
            meta={
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    return ApiResponse(
        success=True,
        data={
            "provider": database_health.provider,
            "configured": database_health.configured,
            "connected": database_health.connected,
        },
        error=None,
        meta={
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@router.get("/health/model", response_model=ApiResponse)
def model_health_check(
    checker: Annotated[ModelHealthChecker, Depends(get_model_health_checker)],
    response: Response,
) -> ApiResponse:
    """Return OpenAI model readiness without exposing credentials."""
    try:
        model_health = checker.check()
    except ModelConnectionError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(
            success=False,
            data=None,
            error={
                "code": "MODEL_CONNECTION_FAILED",
                "message": str(exc),
            },
            meta={
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    if not model_health.configured:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(
            success=False,
            data={
                "provider": model_health.provider,
                "configured": model_health.configured,
                "connected": model_health.connected,
                "model": model_health.model,
            },
            error={
                "code": "MODEL_NOT_CONFIGURED",
                "message": model_health.detail,
            },
            meta={
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    return ApiResponse(
        success=True,
        data={
            "provider": model_health.provider,
            "configured": model_health.configured,
            "connected": model_health.connected,
            "model": model_health.model,
        },
        error=None,
        meta={
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

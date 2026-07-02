from datetime import UTC, datetime

from fastapi import APIRouter

from refunds_ai_api.schemas.responses import ApiResponse

router = APIRouter(tags=["system"])


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

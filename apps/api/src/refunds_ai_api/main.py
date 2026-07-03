import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from refunds_ai_api.routes.application import router as application_router
from refunds_ai_api.routes.health import router as health_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log host-friendly API URLs when the backend starts."""
    logger.info("RefundsAI API")
    logger.info("- Local:   http://localhost:8000")
    logger.info("- Docs:    http://localhost:8000/docs")
    logger.info("- Network: http://0.0.0.0:8000")
    yield


def create_app() -> FastAPI:
    """Create the FastAPI application with foundation routes configured."""
    app = FastAPI(
        title="RefundsAI API",
        description="Backend API for policy-governed refund support workflows.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(application_router)
    app.include_router(health_router)
    return app


app = create_app()

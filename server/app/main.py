import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)


def create_application() -> FastAPI:
    settings = get_settings()

    cors_origins = list(settings.api_cors_origins) or [str(settings.next_public_api_base_url)]

    application = FastAPI(
        title="Trading Dashboard API",
        version="0.1.0",
        default_response_class=ORJSONResponse,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("api.initialized", cors_origins=cors_origins)

    return application


app = create_application()

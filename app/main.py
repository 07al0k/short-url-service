"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router, health_router, redirect_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.database.connection import init_db

logger = logging.getLogger(__name__)

DESCRIPTION = """
A URL shortening service.

* `POST /api/v1/urls` creates a short URL.
* `GET /api/v1/urls/{short_code}` returns its details.
* `GET /{short_code}` redirects to the original URL.
* `GET /health` is a liveness check.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    logger.info("Database ready")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Short URL Service",
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    register_exception_handlers(app)

    # Order matters: the catch-all /{short_code} route has to come last,
    # otherwise it would swallow /health.
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(redirect_router)
    return app


app = create_app()

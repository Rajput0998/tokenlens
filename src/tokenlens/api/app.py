"""FastAPI application factory with lifespan management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tokenlens import __version__


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init DB engine, start WebSocket push. Shutdown: close engine."""
    import asyncio

    from tokenlens.core.database import close_engine, init_engine

    await init_engine()

    # Start WebSocket live push background task
    from tokenlens.api.websocket import _live_push_loop

    push_task = asyncio.create_task(_live_push_loop())

    yield

    push_task.cancel()
    await close_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TokenLens API",
        version=__version__,
        docs_url="/docs",
        lifespan=_lifespan,
    )

    # Health check (outside /api/v1 prefix)
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": __version__}

    # Middleware
    from tokenlens.api.middleware import setup_middleware

    setup_middleware(app)

    # Routes
    from tokenlens.api.routes.analytics import router as analytics_router
    from tokenlens.api.routes.anomalies import router as anomalies_router
    from tokenlens.api.routes.efficiency import router as efficiency_router
    from tokenlens.api.routes.events import router as events_router
    from tokenlens.api.routes.export import router as export_router
    from tokenlens.api.routes.predictions import router as predictions_router
    from tokenlens.api.routes.sessions import router as sessions_router
    from tokenlens.api.routes.settings import router as settings_router
    from tokenlens.api.routes.status import router as status_router

    app.include_router(status_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(predictions_router, prefix="/api/v1")
    app.include_router(efficiency_router, prefix="/api/v1")
    app.include_router(anomalies_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(export_router, prefix="/api/v1")

    # WebSocket
    from tokenlens.api.websocket import register_websockets

    register_websockets(app)

    return app

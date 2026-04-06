"""FastAPI application entrypoint for RAG-OPS."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_ops.api.middleware import RequestContextMiddleware, TimeoutMiddleware
from rag_ops.api.routes.system import router as system_router
from rag_ops.observability import configure_logging
from rag_ops.redis_client import RedisClient
from rag_ops.services.runtime import warm_runtime
from rag_ops.settings import ServiceSettings, get_settings

logger = logging.getLogger(__name__)


def create_app(settings: ServiceSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting %s API in %s mode", active_settings.app_name, active_settings.environment)
        warm_result = await warm_runtime(active_settings)
        app.state.startup_state["warm_status"] = warm_result["status"]
        app.state.startup_state["warm_detail"] = warm_result["detail"]
        yield
        await app.state.redis_client.close()
        logger.info("Stopped %s API", active_settings.app_name)

    app = FastAPI(
        title="RAG-OPS API",
        version="0.1.0",
        description="Service API for datasets, runs, configs, and platform operations.",
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.redis_client = RedisClient(active_settings)
    app.state.startup_state = {
        "warm_status": "skipped",
        "warm_detail": "startup warm-up not executed",
    }
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TimeoutMiddleware, settings=active_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system_router)
    return app


app = create_app()


def main() -> None:
    """Run the API using uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "rag_ops.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()

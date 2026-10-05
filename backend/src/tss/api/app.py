"""FastAPI app factory. P0 skeleton: only /api/health (liveness + DB check)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from tss.core.logging import configure_logging, get_logger
from tss.core.settings import AppConfig, load_config_or_exit
from tss.core.time import utc_now
from tss.db.session import create_engine, create_session_factory

COMPONENT = "api"


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or load_config_or_exit()
    configure_logging(cfg.settings.log_level)
    log = get_logger(COMPONENT)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(cfg.settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        log.info("api started", component=COMPONENT, phase="P0", op="startup")
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="TSS API", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        body: dict[str, Any] = {"service": "api", "time_utc": utc_now().isoformat()}
        try:
            async with app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
            body["db"] = "ok"
            return JSONResponse(body)
        except Exception as exc:  # report any DB failure as unhealthy, never raise
            log.error(
                "health db check failed",
                component=COMPONENT,
                phase="P0",
                op="health",
                error=type(exc).__name__,
            )
            body["db"] = "unavailable"
            body["error"] = f"api/P0/health: database check failed ({type(exc).__name__})"
            return JSONResponse(body, status_code=503)

    return app

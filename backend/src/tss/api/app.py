"""FastAPI app factory: read-only API under /api (Arch §10)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from tss.agents.base import is_db_unreachable
from tss.api import ws as ws_routes
from tss.api.routes import classification, discovery, movers, news, status
from tss.api.routes import config as config_routes
from tss.core.errors import TSSError
from tss.core.logging import configure_logging, get_logger
from tss.core.settings import AppConfig, load_config_or_exit
from tss.core.time import utc_now
from tss.db.session import create_engine, create_session_factory
from tss.realtime.hub import EventHub
from tss.realtime.notify import asyncpg_dsn, listen_loop
from tss.realtime.symbols import live_symbols
from tss.realtime.ticker_gateway import TickerGateway

COMPONENT = "api"


def _error(code: str, message: str, component: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "component": component}},
        status_code=status_code,
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or load_config_or_exit()
    configure_logging(cfg.settings.log_level)
    log = get_logger(COMPONENT)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(cfg.settings)
        factory = create_session_factory(engine)
        hub = EventHub()
        gateway = TickerGateway(hub, lambda: live_symbols(factory))
        app.state.engine = engine
        app.state.session_factory = factory
        app.state.hub = hub
        app.state.gateway = gateway
        tasks = [
            asyncio.create_task(
                listen_loop(asyncpg_dsn(cfg.settings.database_url.get_secret_value()), hub)
            ),
            asyncio.create_task(gateway.run()),
        ]
        log.info("api started", component=COMPONENT, phase="P2", op="startup")
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await engine.dispose()

    app = FastAPI(title="TSS API", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.config = cfg

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(f"http_{exc.status_code}", str(exc.detail), COMPONENT, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _error("invalid_request", f"{where}: {first.get('msg', 'invalid')}", COMPONENT, 422)

    @app.exception_handler(TSSError)
    async def tss_error(_: Request, exc: TSSError) -> JSONResponse:
        return _error("tss_error", exc.message, exc.component, 500)

    def _server_error(request: Request, exc: Exception) -> JSONResponse:
        op = request.url.path.removeprefix("/api/")
        if is_db_unreachable(exc):
            log.error("database unreachable", component=COMPONENT, phase="P1", op=op)
            return _error(
                "database_unavailable", f"api/P1/{op}: database unreachable", COMPONENT, 503
            )
        log.error(
            "unhandled error", component=COMPONENT, phase="P1", op=op, error=type(exc).__name__
        )
        return _error(
            "internal_error", f"api/P1/{op}: unexpected {type(exc).__name__}", COMPONENT, 500
        )

    # Database/connection failures get their own handlers: handled by ExceptionMiddleware, so
    # the 503 is returned cleanly (a bare `Exception` handler re-raises after responding).
    @app.exception_handler(SQLAlchemyError)
    async def db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return _server_error(request, exc)

    @app.exception_handler(OSError)
    async def os_error(request: Request, exc: OSError) -> JSONResponse:
        return _server_error(request, exc)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        return _server_error(request, exc)

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
                phase="P1",
                op="health",
                error=type(exc).__name__,
            )
            body["db"] = "unavailable"
            body["error"] = f"api/P1/health: database check failed ({type(exc).__name__})"
            return JSONResponse(body, status_code=503)

    for module in (status, discovery, classification, movers, news, config_routes):
        app.include_router(module.router, prefix="/api")
    app.include_router(ws_routes.router)
    return app

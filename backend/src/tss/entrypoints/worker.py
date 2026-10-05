"""Worker entrypoint: `python -m tss.entrypoints.worker` (agents + scheduler)."""

from __future__ import annotations

import asyncio
import contextlib
import signal

from tss.agents.base import Deps
from tss.clients.http import HttpClient
from tss.clients.mexc_futures import HOST as FUTURES_HOST
from tss.clients.mexc_futures import MexcFuturesClient
from tss.clients.mexc_spot import HOST as SPOT_HOST
from tss.clients.mexc_spot import MexcSpotClient
from tss.control.pipeline import Controller
from tss.control.scheduler import build_scheduler
from tss.core.logging import configure_logging, get_logger
from tss.core.settings import load_config_or_exit
from tss.db.session import create_engine, create_session_factory

COMPONENT = "worker"


async def main() -> None:
    cfg = load_config_or_exit()
    configure_logging(cfg.settings.log_level)
    log = get_logger(COMPONENT)

    rps = cfg.thresholds.mexc.max_requests_per_second
    http = HttpClient({FUTURES_HOST: rps, SPOT_HOST: rps})
    engine = create_engine(cfg.settings)
    deps = Deps(
        config=cfg,
        session_factory=create_session_factory(engine),
        futures=MexcFuturesClient(http),
        spot=MexcSpotClient(http),
    )
    controller = Controller(deps)
    scheduler = build_scheduler(controller)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    scheduler.start()
    log.info("worker started", component=COMPONENT, phase="P1", op="startup")
    startup = asyncio.create_task(controller.startup())
    try:
        await stop.wait()
    finally:
        log.info("worker stopping", component=COMPONENT, phase="P1", op="shutdown")
        startup.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await startup
        scheduler.shutdown(wait=False)
        await http.aclose()
        await engine.dispose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())

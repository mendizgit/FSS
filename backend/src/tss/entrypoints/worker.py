"""Worker entrypoint: `python -m tss.entrypoints.worker`.

P0 skeleton: validates config, logs startup and idles. Agents and the scheduler arrive in F5.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from tss.core.logging import configure_logging, get_logger
from tss.core.settings import load_config_or_exit

COMPONENT = "worker"


async def main() -> None:
    cfg = load_config_or_exit()
    configure_logging(cfg.settings.log_level)
    log = get_logger(COMPONENT)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info(
        "worker started (P0 skeleton, no agents yet)", component=COMPONENT, phase="P0", op="startup"
    )
    await stop.wait()
    log.info("worker stopped", component=COMPONENT, phase="P0", op="shutdown")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())

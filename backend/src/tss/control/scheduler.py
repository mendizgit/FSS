"""APScheduler wiring (Arch §8). All triggers in UTC; max_instances=1, coalesce=True."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tss.control.pipeline import Controller


def build_scheduler(controller: Controller) -> AsyncIOScheduler:
    cfg = controller.deps.config.thresholds
    scheduler = AsyncIOScheduler(timezone="UTC")
    common = {"max_instances": 1, "coalesce": True}
    scheduler.add_job(
        controller.universe_job,
        "interval",
        hours=cfg.universe.refresh_hours,
        id="universe",
        misfire_grace_time=cfg.universe.refresh_hours * 1800,
        **common,
    )
    scheduler.add_job(
        controller.snapshot_job,
        "cron",
        minute="*/5",
        second=0,
        id="snapshot",
        misfire_grace_time=150,
        **common,
    )
    scheduler.add_job(
        controller.pipeline_job,
        "cron",
        minute="*/15",
        second=20,
        id="pipeline",
        misfire_grace_time=450,
        **common,
    )
    scheduler.add_job(
        controller.retention_job,
        "cron",
        hour=0,
        minute=30,
        id="retention",
        misfire_grace_time=43200,
        **common,
    )
    scheduler.add_job(
        controller.recovery_job,
        "interval",
        seconds=60,
        id="recovery",
        misfire_grace_time=30,
        **common,
    )
    return scheduler

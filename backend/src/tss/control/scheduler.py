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
    # the interval job above is skipped during quiet hours: refresh once when they end
    scheduler.add_job(
        controller.universe_job,
        "cron",
        hour=cfg.quiet_hours.resume_hour_ist,
        minute=0,
        second=0,
        timezone="Asia/Kolkata",
        id="universe_resume",
        misfire_grace_time=1800,
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
        controller.signal_job,
        "cron",
        # every 5-min bar close, +5 s; at :00/:15/:30/:45 the pipeline (+20 s) runs it once more
        # right after it saves the new selection
        minute="*/5",
        second=5,
        id="signal",
        misfire_grace_time=150,
        **common,
    )
    scheduler.add_job(
        controller.news_job,
        "cron",
        minute="*/15",
        second=50,
        id="news",
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
    scheduler.add_job(
        controller.pause_watch_job,
        "interval",
        seconds=10,
        id="pause_watch",
        misfire_grace_time=10,
        **common,
    )
    scheduler.add_job(
        controller.restart_watch_job,
        "interval",
        seconds=5,
        id="restart_watch",
        misfire_grace_time=5,
        **common,
    )
    scheduler.add_job(
        controller.mexc_recovery_job,
        "interval",
        seconds=15,
        id="mexc_recovery",
        misfire_grace_time=10,
        **common,
    )
    return scheduler

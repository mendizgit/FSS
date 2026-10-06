"""POST /api/flags/{key} (News / Telegram switches) and POST /api/control/run (Pause / Start)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.api.schemas.models import PauseOut
from tss.control.flags import RUN, news_on, telegram_on
from tss.control.schedule import pause_state
from tss.core.settings import AppConfig
from tss.core.time import utc_now
from tss.db.repositories import ops

router = APIRouter()


class FlagIn(BaseModel):
    enabled: bool


class FlagsOut(BaseModel):
    flags: dict[str, bool]


@router.post("/flags/{key}", response_model=FlagsOut)
async def set_flag(
    key: Literal["news", "telegram"],
    body: FlagIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[AppConfig, Depends(get_config)],
) -> FlagsOut:
    if key == "telegram" and not cfg.settings.telegram_configured:
        raise HTTPException(
            status_code=409,
            detail="api/P5/set_flag: Telegram credentials are not configured in .env",
        )
    await ops.set_flag(session, key, body.enabled, utc_now())
    await session.commit()
    flags = await ops.get_flags(session)
    return FlagsOut(
        flags={
            "news": news_on(flags),
            "telegram": telegram_on(
                flags, cfg.settings.telegram_configured, cfg.settings.telegram_paused
            ),
        }
    )


class RunIn(BaseModel):
    enabled: bool  # True = Start, False = Pause


@router.post("/control/run", response_model=PauseOut)
async def set_run(
    body: RunIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    cfg: Annotated[AppConfig, Depends(get_config)],
) -> PauseOut:
    """Dashboard Pause / Start. Pause holds until the next resume hour (06:00 IST) or Start;
    Start holds until the next pause hour (00:00 IST) or Pause. See control/schedule.pause_state."""
    now = utc_now()
    await ops.set_flag(session, RUN, body.enabled, now)
    await session.commit()
    q = cfg.thresholds.quiet_hours
    state = pause_state(now, body.enabled, now, q.pause_hour_ist, q.resume_hour_ist)
    return PauseOut(
        paused=state.paused, manual=state.manual, reason=state.reason, until=state.until
    )

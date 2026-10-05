"""POST /api/flags/{key}: persistent on/off switches for News collection and Telegram alerts."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tss.api.deps import get_config, get_session
from tss.control.flags import news_on, telegram_on
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

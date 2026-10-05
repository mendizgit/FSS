"""GET /api/config/thresholds (effective thresholds, no secrets)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from tss.api.deps import get_config
from tss.core.settings import AppConfig

router = APIRouter()


@router.get("/config/thresholds")
async def thresholds(cfg: Annotated[AppConfig, Depends(get_config)]) -> dict[str, Any]:
    return cfg.thresholds.model_dump()

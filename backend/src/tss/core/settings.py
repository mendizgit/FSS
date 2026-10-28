"""Settings: env via pydantic-settings (secrets as SecretStr) + validated YAML config."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from tss.core.errors import ConfigError

COMPONENT = "settings"
PHASE = "startup"
EXIT_CONFIG = 78  # EX_CONFIG

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """Environment settings. Never print this object (it holds secrets)."""

    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    database_url: SecretStr
    display_tz: str = "Asia/Kolkata"
    retention_days: int = Field(default=5, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cryptopanic_api_key: SecretStr | None = None
    telegram_bot_token: SecretStr | None = None  # Phase 5
    telegram_chat_id: str | None = None  # Phase 5
    telegram_alerts: str = "on"  # "off" pauses alerts without removing the credentials

    @property
    def telegram_configured(self) -> bool:
        """Credentials present (an empty value in .env counts as unset)."""
        token = (
            self.telegram_bot_token.get_secret_value().strip() if self.telegram_bot_token else ""
        )
        return bool(token and (self.telegram_chat_id or "").strip())

    @property
    def telegram_paused(self) -> bool:
        """TELEGRAM_ALERTS=off (also false / 0 / no / paused) pauses the notifier."""
        return self.telegram_alerts.strip().lower() in {"off", "false", "0", "no", "paused"}

    @property
    def telegram_enabled(self) -> bool:
        """Alerts are sent only with credentials and while not paused."""
        return self.telegram_configured and not self.telegram_paused


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UniverseCfg(_Strict):
    quote_asset: str
    refresh_hours: int = Field(gt=0)
    pinned_symbols: list[str]


class SignalsCfg(_Strict):
    majors: list[str]
    min_other_factors: int = Field(default=2, ge=0, le=4)  # besides the mandatory 1H M trend
    alert_cooldown_minutes: int = Field(default=30, ge=0)  # per symbol and side


class PaperCfg(_Strict):
    """Dummy-money test of the 15m entry signals (analysis only: no orders, public prices)."""

    enabled: bool = True
    start_balance_usdt: float = Field(default=500, gt=0)
    leverage: float = Field(default=10, ge=1)
    margin_per_trade_usdt: float = Field(default=50, gt=0)
    stop_pct: float = Field(default=1.0, gt=0)  # price move against the entry
    reward_risk: float = Field(default=2.0, gt=0)  # target = reward_risk x stop distance
    timeout_minutes: int = Field(default=240, gt=0)
    fee_pct: float = Field(default=0.02, ge=0)  # per side, on notional
    slippage_pct: float = Field(default=0.02, ge=0)  # per side, against the trade


class FgiPaperCfg(_Strict):
    """Dummy-money forward test of the FGI Pro strategy on the 15m chart (analysis only)."""

    enabled: bool = False
    pool_size: int = Field(default=80, gt=0)  # top USDT perpetuals by 24h turnover
    start_balance_usdt: float = Field(default=500, gt=0)
    leverage: float = Field(default=10, ge=1)
    margin_per_trade_usdt: float = Field(default=50, gt=0)
    max_open: int = Field(default=10, gt=0)
    min_score: int = Field(default=4, ge=1, le=6)  # of the 6 confluence factors
    adx_min: float = Field(default=35, gt=0)
    use_4h: bool = False  # False: trend filter is the 1H SuperTrend only
    stop_cap_pct: float = Field(default=2.0, gt=0)  # stop never wider than this from the entry
    tp1_atr: float = Field(default=1.5, gt=0)
    tp2_atr: float = Field(default=3.5, gt=0)
    tp1_fraction: float = Field(default=0.5, gt=0, lt=1)
    fee_pct: float = Field(default=0.02, ge=0)  # per side, on notional
    slippage_pct: float = Field(default=0.02, ge=0)  # per side, against the trade


class LiquidityCfg(_Strict):
    min_turnover_24h_usdt: float = Field(ge=0)
    min_oi_notional_usdt: float = Field(ge=0)


class KlineCfg(_Strict):
    interval: str
    backfill_bars: int = Field(gt=0)


class MomentumCfg(_Strict):
    pool_size: int = Field(gt=0)
    rvol_lookback_bars: int = Field(gt=0)
    min_rvol: float = Field(gt=0)
    min_abs_price_change_15m_pct: float = Field(ge=0)
    top_n: int = Field(gt=0)
    rank_by: Literal["rvol_15m"]


class MoversCfg(_Strict):
    top_n: int = Field(gt=0)
    period: Literal["utc_day"]


class DeadbandCfg(_Strict):
    price_pct: float = Field(ge=0)
    oi_pct: float = Field(ge=0)
    volume_pct: float = Field(ge=0)
    funding_delta: float = Field(ge=0)


class ClassificationCfg(_Strict):
    windows: list[Literal["1h", "4h"]]
    deadband: DeadbandCfg
    crowded_long_funding: float
    crowded_short_funding: float
    stale_after_s: int = Field(gt=0)
    snapshot_match_tolerance_s: int = Field(gt=0)


class ControlCfg(_Strict):
    cycle_budget_s: int = Field(gt=0)
    breaker_failures: int = Field(gt=0)
    breaker_cooldown_s: int = Field(gt=0)


class QuietHoursCfg(_Strict):
    """Daily window (IST wall clock) in which the data/signal jobs do not run."""

    pause_hour_ist: int = Field(ge=0, le=23)
    resume_hour_ist: int = Field(ge=0, le=23)


class MexcCfg(_Strict):
    max_requests_per_second: float = Field(gt=0)


class Thresholds(_Strict):
    universe: UniverseCfg
    signals: SignalsCfg
    paper: PaperCfg = Field(default_factory=PaperCfg)
    paper_fgi: FgiPaperCfg = Field(default_factory=FgiPaperCfg)
    liquidity: LiquidityCfg
    kline: KlineCfg
    momentum: MomentumCfg
    movers: MoversCfg
    classification: ClassificationCfg
    control: ControlCfg
    quiet_hours: QuietHoursCfg
    mexc: MexcCfg


class Denylist(_Strict):
    symbols: list[str] = Field(default_factory=list)
    suffixes: list[str] = Field(default_factory=list)  # e.g. tokenized stocks: STOCK_USDT

    def is_denied(self, symbol: str) -> bool:
        return symbol in self.symbols or any(symbol.endswith(s) for s in self.suffixes)


class RssSource(_Strict):
    name: str
    url: str
    enabled: bool = True


class CryptoPanicCfg(_Strict):
    enabled: bool = True


class NewsSources(_Strict):
    rss: list[RssSource]
    cryptopanic: CryptoPanicCfg
    symbol_stoplist: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Validated application config. `settings` holds secrets: never log or print it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    settings: Settings
    thresholds: Thresholds
    denylist: Denylist
    news_sources: NewsSources

    def __repr__(self) -> str:  # defensive: never expose secrets via repr
        return "AppConfig(<redacted>)"


def config_dir() -> Path:
    override = os.environ.get("TSS_CONFIG_DIR")
    return Path(override) if override else _BACKEND_DIR / "config"


def _safe_errors(exc: PydanticValidationError) -> str:
    """Field paths and reasons only. Never include input values (may be secrets)."""
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['type']}" for err in exc.errors()
    )


def _load_yaml[T: BaseModel](directory: Path, name: str, model: type[T]) -> T:
    path = directory / name
    operation = f"load {name}"
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(COMPONENT, PHASE, operation, f"file not found: {path}") from exc
    except (yaml.YAMLError, OSError) as exc:
        raise ConfigError(COMPONENT, PHASE, operation, f"cannot parse {name}: {exc}") from exc
    try:
        return model.model_validate(raw)
    except PydanticValidationError as exc:
        raise ConfigError(
            COMPONENT, PHASE, operation, f"invalid {name}: {_safe_errors(exc)}"
        ) from exc


def load_config(directory: Path | None = None) -> AppConfig:
    """Load env settings and validate all YAML config. Raises ConfigError (component-named)."""
    cfg_dir = directory or config_dir()
    try:
        # database_url is required; pydantic-settings reads it from the environment/.env.
        settings = Settings()
    except PydanticValidationError as exc:
        names = ", ".join(str(e["loc"][0]).upper() for e in exc.errors() if e["loc"])
        raise ConfigError(
            COMPONENT,
            PHASE,
            "load env settings",
            f"missing or invalid variables: {names}",
        ) from exc
    return AppConfig(
        settings=settings,
        thresholds=_load_yaml(cfg_dir, "thresholds.yaml", Thresholds),
        denylist=_load_yaml(cfg_dir, "denylist.yaml", Denylist),
        news_sources=_load_yaml(cfg_dir, "news_sources.yaml", NewsSources),
    )


def load_config_or_exit(directory: Path | None = None) -> AppConfig:
    """Entrypoint helper: on invalid config print the component-named error and exit 78."""
    try:
        return load_config(directory)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from exc


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()

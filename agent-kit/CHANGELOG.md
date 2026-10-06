# Agent Kit Changelog

## v1.3.4 — 2026-10-06 (user-approved Heikin-Ashi signals, branch feat/heikin-ashi)
- Signals now run on Heikin-Ashi candles (signal bars 5m/15m/1h and the 1h/4h HTF series). New: `indicators/heikin_ashi.py`, `agents/signal_ha.py` (`SignalAgentHA`, agent name stays `signal`), wired in `control/pipeline.py`. Old `agents/signal.py` is kept unused for rollback (swap the import back). Classification is unchanged (real candles). Alert text unchanged. Telegram no longer pushes TD_BULL / TD_BEAR (user request; BUY/SELL/BULL_T/BEAR_T on 5m+15m remain; TD events are still computed and shown on the dashboard, and stay unnotified). No migration; existing rows stay. HA values (price_vs_vwap, zone) are in HA price space. TradingView parity still unproven.

## v1.3.3 — 2026-10-05 (user-approved signal coverage change)
- Telegram alerts no longer carry the "Not financial advice" footer (user request); the `✗ Against the 4H trend` line remains when applicable. The dashboard footer notice and the `telegram_setup test` disclaimer were removed as well (user request, overrides PROJECT_GUIDELINES/ui-design notice rules; docs updated). README keeps its own disclaimer line.
- Telegram now also pushes TD_BULL / TD_BEAR (user request; was BUY/SELL/bullT/bearT only). TD alert: `Signal : —`, `Trend : TD Bull|TD Bear`. Scope = every signal-engine symbol (momentum-selected + majors). Alerts are sent for 5m and 15m only (1h stays dashboard-only) and carry `Bar close : HH:MM IST` (close time of the signal bar).
- Persistent switches: table `control_flags` (migration 7a1d3c9e5b20), `POST /api/flags/{news|telegram}` {enabled}, `/api/status.flags`. News off = news job skipped (no fetch). Telegram needs credentials; a dashboard choice overrides `TELEGRAM_ALERTS` in .env, with no choice the .env value decides. Header buttons "News feed: on/off" and "Telegram: on/off". First write endpoint (behind the same Caddy login).
- Zone column restored in the Signals table (user request): `signals.zone_position` (migration c5a2d7e91f08), API field and GUI column (Top zone+ / Top zone / Mid / Bottom zone / Bottom zone+). Filled on the next signal run.
- Signals cleanup (user request): removed htf_supertrend, local_supertrend, consolidated_trend, long/short score+grade, rsi_divergence, sr_letter, zone_position from the GUI, `/api/signals/latest`, the `signals` table (migration b3e8f01c6d44 drops the columns) and `SignalSnapshot`. Kept: m_trend, last_event, bars_ago, against_htf (event flag, alerts), price_vs_vwap. Indicator series math is unchanged (events/parity unaffected); the unused `zone_position` helper stays in indicators/zones.py.
- GUI: header toggle "News" hides/shows the News panel on md+ (remembered in localStorage); with News hidden the Classification/Signals-Movers columns widen (xl: 50 / 50).
- Momentum thresholds: `pool_size` 50→80, `min_rvol` 1.5→1.2, `min_abs_price_change_15m_pct` 1.5→0.8 (`top_n` 20→30). Arch §5.3 text/§13 updated.
- Signal engine symbols = momentum-selected + `signals.majors` only; pinned symbols no longer add signals (still ticked, classified, ranked).
- New config `quiet_hours` (pause 00:00 IST, resume 06:00 IST): snapshot/movers/pipeline/signal/news (and so notifier) do not run in the window; only retention keeps its schedule (universe pauses too and refreshes once at 06:00 IST via cron `universe_resume`); API/WS/ticks stay up; /api/status reports state PAUSED. After resume 1h/4h classification windows need history again (1h/4h) and show UNKNOWN until then.
- Auto-start after reboot: docker is enabled in systemd and every service has `restart: unless-stopped`.
- Signal job runs right after each 15-min pipeline (:00/:15/:30/:45); the 5-min cron (+20 s, matching the 5-min snapshot window) covers the other boundaries.

## v1.3.2 — 2026-10-05 (user-requested dashboard change)
- New config `signals.majors` (BTC, ETH, SOL, XRP): their signals are always computed and shown on a new "Majors" tab of the Signals panel; the "Momentum" tab shows the selected symbols. `/api/signals/latest` rows carry `group`.
- Live ticker now subscribes to every price shown (selected, pinned, majors, movers, pool) and re-subscribes on `movers_updated`; movers / pool day-change is recomputed live from the tick and the day open.

## v1.3.1 — 2026-10-05 (P0 preflight findings)
- Arch §3.1: kline `time` is in seconds; the last bar returned can be the forming one (drop it, per §5.2).
- LAN port: host/LAN port is now 8088 (8080 is used by another local app). Caddy still listens on :8080 inside its container; compose maps `<UBUNTU_LAN_IP>:8088:8080`. Updated Arch §2/§12 text, ER §12/§16, skills/deployment.md, README.
- Arch §4: `state` codes confirmed from MEXC docs (0 enabled, 1 delivery, 2 delivered, 3 offline, 4 paused); universe filter uses `state == 0`.

## v1.3 — 2026-10-05
- Simplified memory to a **single file**, `agent-kit/MEMORY.md`, updated by in-place edits.
- Removed: `memory/` folder (STATE, JOURNAL, HISTORY, CODEMAP, DECISIONS), `reports/`, the Stop hook, `/resume`, `/checkpoint`, `/phase-close`.
- Kept: the SessionStart hook (injects MEMORY.md and git status, with a drift check), `INDEX.md`, and one command, `/save`.
- Phase-end reports are now a short chat summary (EXECUTION_RULES §17).

## v1.2 — 2026-10-05
- Memory system added: `agent-kit/memory/` (STATE, JOURNAL, HISTORY, CODEMAP, DECISIONS).
- `agent-kit/INDEX.md` maps each feature to the doc sections it needs, so docs are loaded by section rather than in full.
- `.claude/` additions:
  - SessionStart hook injects STATE + git summary and flags drift.
  - Stop hook reminds Claude to checkpoint.
  - New slash commands: `/resume`, `/checkpoint`, `/phase-close`.
- CLAUDE.md and EXECUTION_RULES §1 now use the context-loading protocol. EXECUTION_RULES gains §19 Memory protocol.

## v1.1 — 2026-10-05
- MEXC is now the only market-data source. CMC was removed from the architecture, blueprint, env, tables and preflight.
- Liquidity gate: 24h turnover ≥ $1M and OI notional ≥ $500k. This replaces the market-cap filter.
- Discovery funnel: liquid universe → top 50 movers pool by RVOL → Gate 2 (|Δp 15m| ≥ 1.5 % and RVOL ≥ 1.5×) → top 20.
- Nothing is excluded by asset type. BTC_USDT and ETH_USDT are pinned as market context.
- New F12 Market Movers: top 10 gainers and losers since 00:00 UTC, shown below the Signals panel.
- New tables: `klines_15m`, `daily_opens`, `momentum_rankings`, `market_movers`.
- Removed tables: `cmc_assets`, `momentum_selections`.
- Out of scope: order flow, footprint, CVD, order book.
- Zero-fee badge added (display only, if MEXC returns fee fields).

## v1.0 — 2026-10-05
- Initial approved kit (CMC + MEXC).

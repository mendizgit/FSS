# Skill — Market-Data Agents & Calculations

## Role

Act as a senior Python data engineer building reliable, rate-limit-aware collectors and deterministic calculations for crypto market data.

## Agent pattern

Every agent subclasses `agents/base.py::BaseAgent`:

```python
async def run(self, cycle_id: UUID, now: datetime) -> AgentResult:
    # 1. fetch via clients
    # 2. validate (Pydantic)
    # 3. compute via domain (pure)
    # 4. persist via repositories
    # 5. return counts
```

- `BaseAgent` owns:
  - the `agent_runs` row (RUNNING → SUCCESS/PARTIAL/FAILED/SKIPPED)
  - timing
  - exception wrapping into `TSSError`
  - the `NOTIFY` call
- Agents are idempotent per `(agent, aligned timestamp)`. A re-run must not duplicate rows (use upserts).
- `now` is injected by the scheduler. Domain code never calls the clock.

## Clients

- One module per source. Each method maps 1:1 to an endpoint and returns typed models.
- Parse numbers explicitly. MEXC returns some numerics as strings. Treat empty or missing as `None`, never `0`.
- Respect the rate limits in `config/thresholds.yaml`. Batch endpoints over per-symbol loops.
- Record the endpoint path (not full URL with params containing keys) in the error context.

## Data integrity

- Validate every external payload. On a schema mismatch, raise `DataSourceError` naming the field. Do not coerce silently.
- Never fabricate: missing becomes `None` plus a reason code (`unavailable_on_plan`, `no_spot_market`, `history_unavailable`, `source_error`).
- Klines: drop the forming bar (`open_time + interval > now`). Detect gaps and flag them as UNRELIABLE reasons.
- Snapshot matching uses the tolerance in config. Never interpolate.
- Prefer turnover (USDT `amount`) for volume comparisons across contracts.
- `klines_15m` is the shared store of closed 15m bars. Sync incrementally (fetch only bars newer than the latest stored bar, plus 1 for correction). Backfill `kline.backfill_bars` on the first run for a symbol.

## Calculations

- Pure functions with type hints in `domain/`. Every formula from Arch §5–§6 has a unit check with a hand-computed fixture.
- Use `Decimal` or `float64` consistently: `float64` for analytics, `numeric` in the DB for prices.
- Percent values are in percent units (1.5 = 1.5 %). Funding is stored as a raw rate (0.0001 = 0.01 %).

## Scheduling

- Cron-aligned triggers (UTC). Use `max_instances=1` and `coalesce=True`. Set the misfire grace to half the interval.
- Dependencies run inside a pipeline function with a shared `cycle_id`. They are not separately scheduled jobs racing each other.

## Logging

- structlog JSON with bound `component`, `phase`, `op` and `cycle_id`.
- One summary line per run (counts, duration). Use debug level for per-symbol details.
- Never log request headers, query strings containing keys, or settings.

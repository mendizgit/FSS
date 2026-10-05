"""Bar-by-bar parity check of the Python port against TradingView exports (skills/pine-port.md).

Reads backend/tests/fixtures/tv/<SYMBOL>_<TF>.csv (see the README there), runs the port on the
exported OHLCV and compares the plotted series after a 500-bar warm-up:
  R / S / M, EMA 1-3, VWAP: relative error <= 1e-6
  bullT, bearT, BUY, SELL, TD bull, TD bear, r / s letters: exact match on the same bar
Higher-timeframe-dependent tags ("against 4H") are merged, as that part is a documented
deviation. Mismatches are reported with bar time and values; nothing is tuned to hide them.

Exit codes: 0 all match, 1 mismatches, 2 no fixtures found (parity UNPROVEN).

Run: uv run python scripts/parity_check.py [fixtures_dir]
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

from tss.indicators.fgi_v3 import Bars, HtfContext, compute

WARMUP = 500
REL_TOL = 1e-6
DEFAULT_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "tv"

LINES = {
    "R": "line_r",
    "S": "line_s",
    "EMA 1": "ema1",
    "EMA 2": "ema2",
    "EMA 3": "ema3",
    "VWAP": "vwap",
}
EVENT_COLUMNS: dict[str, list[str]] = {
    "bullT": ["bullT", "bullT (against 4H)"],
    "bearT": ["bearT", "bearT (against 4H)"],
    "BUY": ["BUY", "BUY (against 4H)"],
    "SELL": ["SELL", "SELL (against 4H)"],
    "TD bull": ["TD bull"],
    "TD bear": ["TD bear"],
    "r": ["r (setup 1)", "r (setup 2)"],
    "s": ["s (setup 1)", "s (setup 2)"],
}


def num(raw: str | None) -> float:
    if raw is None or raw.strip() in ("", "NaN", "nan"):
        return math.nan
    try:
        return float(raw)
    except ValueError:
        return math.nan


def parse_time(raw: str) -> datetime:
    raw = raw.strip()
    if raw.isdigit():
        return datetime.fromtimestamp(int(raw), tz=UTC)
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)


def present(row: dict[str, str], columns: list[str]) -> bool:
    return any(not math.isnan(num(row.get(c))) and num(row.get(c)) != 0 for c in columns)


def load(path: Path) -> tuple[Bars, list[dict[str, str]]]:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    lower = {k.lower(): k for k in rows[0]}
    bars = Bars(
        open_time=[parse_time(r[lower["time"]]) for r in rows],
        open=[num(r[lower["open"]]) for r in rows],
        high=[num(r[lower["high"]]) for r in rows],
        low=[num(r[lower["low"]]) for r in rows],
        close=[num(r[lower["close"]]) for r in rows],
        volume=[num(r.get(lower.get("volume", "volume"))) for r in rows],
    )
    return bars, rows


def check_file(path: Path) -> list[str]:
    bars, rows = load(path)
    n = len(bars)
    if n <= WARMUP + 10:
        return [f"{path.name}: only {n} bars; need more than {WARMUP + 10}"]
    # HTF-dependent outputs are not compared, so the context is neutral.
    neutral = HtfContext([0] * n, [math.nan] * n, [math.nan] * n)
    result = compute(bars, neutral)
    problems: list[str] = []

    for title, attr in LINES.items():
        if title not in rows[0]:
            continue
        worst, at = 0.0, -1
        series = getattr(result, attr)
        for i in range(WARMUP, n):
            exp, got = num(rows[i].get(title)), series[i]
            if math.isnan(exp) and math.isnan(got):
                continue
            err = (
                math.inf
                if (math.isnan(exp) != math.isnan(got))
                else abs(got - exp) / max(abs(exp), 1e-12)
            )
            if err > worst:
                worst, at = err, i
        status = "OK" if worst <= REL_TOL else "MISMATCH"
        print(f"  {path.name:20s} {title:8s} max rel err {worst:.3e}  {status}")
        if worst > REL_TOL:
            problems.append(
                f"{path.name} {title}: bar {bars.open_time[at].isoformat()} "
                f"expected {rows[at].get(title)} got {getattr(result, attr)[at]}"
            )

    if "M - uptrend" in rows[0] and "M - downtrend" in rows[0]:
        bad = [
            i
            for i in range(WARMUP, n)
            if (result.trend[i] == 1) != (not math.isnan(num(rows[i].get("M - uptrend"))))
        ]
        print(
            f"  {path.name:20s} {'M trend':8s} mismatching bars {len(bad)}  "
            f"{'OK' if not bad else 'MISMATCH'}"
        )
        problems += [f"{path.name} M trend: {bars.open_time[i].isoformat()}" for i in bad[:5]]

    mine = {
        "bullT": result.bull_t,
        "bearT": result.bear_t,
        "BUY": result.buy,
        "SELL": result.sell,
        "TD bull": result.td_bull,
        "TD bear": result.td_bear,
        "r": result.r_letter,
        "s": result.s_letter,
    }
    for name, columns in EVENT_COLUMNS.items():
        if not any(c in rows[0] for c in columns):
            continue
        diff = [i for i in range(WARMUP, n) if present(rows[i], columns) != mine[name][i]]
        print(
            f"  {path.name:20s} {name:8s} event mismatches {len(diff):4d}  "
            f"{'OK' if not diff else 'MISMATCH'}"
        )
        for i in diff[:5]:
            problems.append(
                f"{path.name} {name} bar {bars.open_time[i].isoformat()}: "
                f"TradingView={present(rows[i], columns)} port={mine[name][i]}"
            )
    return problems


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    files = sorted(directory.glob("*.csv"))
    if not files:
        print(
            f"No TradingView exports in {directory}.\n"
            f"Parity is UNPROVEN: see {directory}/README.md "
            "for how to export (3 symbols x 5m/15m/1h)."
        )
        return 2
    all_problems: list[str] = []
    for f in files:
        print(f.name)
        all_problems += check_file(f)
    if all_problems:
        print(f"\n{len(all_problems)} mismatch(es):")
        for p in all_problems[:50]:
            print("  -", p)
        return 1
    print(f"\nParity OK for {len(files)} file(s) after a {WARMUP}-bar warm-up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

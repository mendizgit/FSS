import type { SignalRow } from "@/types/api";

export interface EventMeta {
  label: string;
  tone: "up" | "down" | "muted";
  meaning: string;
}

export const EVENT_META: Record<string, EventMeta> = {
  BUY: { label: "BUY", tone: "up", meaning: "Trend flipped up after RSI was oversold (≤ 30) within the last 20 bars." },
  SELL: { label: "SELL", tone: "down", meaning: "Trend flipped down after RSI was overbought (≥ 70) within the last 20 bars." },
  BULL_T: { label: "bullT", tone: "up", meaning: "M turned up: price broke out of the held R / S band." },
  BEAR_T: { label: "bearT", tone: "down", meaning: "M turned down: price broke out of the held R / S band." },
  TD_BULL: { label: "TD ▲", tone: "up", meaning: "EMA 9/21 cross or local SuperTrend flip while both point up." },
  TD_BEAR: { label: "TD ▼", tone: "down", meaning: "EMA 9/21 cross or local SuperTrend flip while both point down." },
  NONE: { label: "none", tone: "muted", meaning: "No event in the available history." },
};

export const ZONE_LABEL: Record<string, { text: string; tone: "up" | "down" | "muted"; meaning: string }> = {
  TOP_SUB: { text: "Top zone+", tone: "down", meaning: "Close is inside or beyond the sub zone of the upper extreme zone." },
  TOP_MAIN: { text: "Top zone", tone: "down", meaning: "Close is inside the main upper extreme zone." },
  BOTTOM_SUB: { text: "Bottom zone+", tone: "up", meaning: "Close is inside or beyond the sub zone of the lower extreme zone." },
  BOTTOM_MAIN: { text: "Bottom zone", tone: "up", meaning: "Close is inside the main lower extreme zone." },
  MID: { text: "Mid", tone: "muted", meaning: "Between the extreme zones." },
};


export const TF_MINUTES: Record<string, number> = { "5m": 5, "15m": 15, "1h": 60 };

/** "Fresh" window per timeframe, in bars: 5m 0-5, 15m 0-2 (the 1h row is not badged). */
export const FRESH_MAX_BARS: Record<string, number> = { "5m": 5, "15m": 2 };
/** The 1h confirmation event may be 0-10 bars old. */
export const HTF_EVENT_MAX_BARS = 10;

const BULL_EVENTS = new Set(["BUY", "BULL_T"]);
const BEAR_EVENTS = new Set(["SELL", "BEAR_T"]);

export function isFresh(row: SignalRow): boolean {
  const max = FRESH_MAX_BARS[row.timeframe];
  return max !== undefined && row.last_event !== "NONE" && row.bars_ago !== null && row.bars_ago <= max;
}

export type Bias = "long" | "short" | "neutral";

export interface Setup {
  bias: Bias;
  /** 5m/15m row that triggered the setup (the fresher one when both did). */
  trigger: SignalRow | null;
  /** Against the 4H trend, as recorded on the triggering event. */
  againstHtf: boolean | null;
  minutesAgo: number;
}

function side(rows: SignalRow[], dir: "UP" | "DOWN", events: Set<string>): Setup | null {
  const trendIs = (row: SignalRow) =>
    row.m_trend === dir || row.m_trend === (dir === "UP" ? "BULL" : "BEAR");
  const newest = (row: SignalRow, maxBars: number) =>
    row.recent_events.filter((e) => events.has(e.event) && e.bars_ago <= maxBars).sort((a, b) => a.bars_ago - b.bars_ago)[0];
  const h1 = rows.find((r) => r.timeframe === "1h");
  if (!h1 || !trendIs(h1) || !newest(h1, HTF_EVENT_MAX_BARS)) return null;
  let best: Setup | null = null;
  for (const row of rows) {
    const max = FRESH_MAX_BARS[row.timeframe];
    if (row.timeframe === "1h" || max === undefined || !trendIs(row)) continue;
    const ev = newest(row, max);
    if (!ev) continue;
    const minutesAgo = ev.bars_ago * (TF_MINUTES[row.timeframe] ?? 5);
    if (best === null || minutesAgo < best.minutesAgo) {
      best = { bias: dir === "UP" ? "long" : "short", trigger: row, againstHtf: ev.against_htf, minutesAgo };
    }
  }
  return best;
}

/**
 * Long: a BUY/bullT within the fresh window on 5m (0-5 bars) or 15m (0-2 bars) with M trend Up, plus a
 * BUY/bullT on 1h within 0-10 bars with 1h M trend Up. Events come from the stored history
 * (recent_events), not only the newest one. Short is the mirror. Both or neither: neutral.
 */
export function classifySetup(rows: SignalRow[]): Setup {
  const long = side(rows, "UP", BULL_EVENTS);
  const short = side(rows, "DOWN", BEAR_EVENTS);
  if (long && !short) return long;
  if (short && !long) return short;
  return { bias: "neutral", trigger: null, againstHtf: null, minutesAgo: Number.POSITIVE_INFINITY };
}

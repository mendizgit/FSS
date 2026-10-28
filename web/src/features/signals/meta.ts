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

/** "Fresh" window per timeframe, in bars: 5m 0-5, 15m 0-2 (the 1h row is not badged). The Long / Short
 * entry itself is decided by the backend (domain/setups.py) and arrives as `setup` in the API. */
export const FRESH_MAX_BARS: Record<string, number> = { "5m": 5, "15m": 2 };
export function isFresh(row: SignalRow): boolean {
  const max = FRESH_MAX_BARS[row.timeframe];
  return max !== undefined && row.last_event !== "NONE" && row.bars_ago !== null && row.bars_ago <= max;
}

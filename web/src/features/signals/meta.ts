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

export const DIVERGENCE_LABEL: Record<string, { text: string; tone: "up" | "down"; meaning: string }> = {
  POS_REG: { text: "Bull div", tone: "up", meaning: "Regular bullish RSI divergence on the newest closed bar." },
  NEG_REG: { text: "Bear div", tone: "down", meaning: "Regular bearish RSI divergence on the newest closed bar." },
};

export const TF_MINUTES: Record<string, number> = { "5m": 5, "15m": 15, "1h": 60 };

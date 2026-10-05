import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Minus,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

export interface StateMeta {
  label: string;
  icon: LucideIcon;
  tone: "up" | "down" | "muted" | "warn";
  outlined: boolean;
  meaning: string;
}

export const STATE_META: Record<string, StateMeta> = {
  LONG_BUILDUP: {
    label: "Long build-up",
    icon: TrendingUp,
    tone: "up",
    outlined: false,
    meaning: "Price, open interest and futures volume rising: trend confirmation (long).",
  },
  SHORT_BUILDUP: {
    label: "Short build-up",
    icon: TrendingDown,
    tone: "down",
    outlined: false,
    meaning: "Price falling while open interest and futures volume rise: short build-up.",
  },
  SHORT_COVERING: {
    label: "Short covering",
    icon: ArrowUpRight,
    tone: "up",
    outlined: true,
    meaning: "Price rising while open interest falls: short squeeze / covering.",
  },
  LONG_UNWINDING: {
    label: "Long unwinding",
    icon: ArrowDownRight,
    tone: "down",
    outlined: true,
    meaning: "Price and open interest both falling: long liquidation / weak trend.",
  },
  NEUTRAL: {
    label: "Neutral",
    icon: Minus,
    tone: "muted",
    outlined: false,
    meaning: "None of the build-up / covering / unwinding patterns apply.",
  },
  UNRELIABLE: {
    label: "Unreliable",
    icon: AlertTriangle,
    tone: "warn",
    outlined: true,
    meaning: "Not enough trustworthy data to classify; see the reasons.",
  },
};

export const FLAG_META: Record<string, { abbr: string; meaning: string }> = {
  FUNDING_CONFIRMS: {
    abbr: "FUND✓",
    meaning: "Funding is moving in the same direction as the build-up.",
  },
  CROWDED_LONG: { abbr: "CRWD-L", meaning: "Funding is at or above the crowded-long threshold." },
  CROWDED_SHORT: { abbr: "CRWD-S", meaning: "Funding is at or below the crowded-short threshold." },
  SQUEEZE_RISK: {
    abbr: "SQZ",
    meaning: "Short covering or short build-up while shorts are crowded: squeeze risk.",
  },
  SPOT_CONFIRMED: { abbr: "SPOT✓", meaning: "Spot volume is rising too." },
  TF_CONFLICT: { abbr: "TF≠", meaning: "The 1h and 4h states point in opposite directions." },
  WARMING_UP: {
    abbr: "WARM",
    meaning: "Open-interest / funding history is shorter than the window.",
  },
  LIQUIDATIONS_UNAVAILABLE: {
    abbr: "LIQ n/a",
    meaning: "MEXC does not publish a liquidation feed; liquidations are never shown.",
  },
};

export const REASON_TEXT: Record<string, string> = {
  snapshot_stale: "The newest market snapshot is older than 10 minutes.",
  missing_price: "Price history for the window is incomplete.",
  missing_futures_volume: "Futures volume for the window is incomplete.",
  missing_oi: "Open-interest data for the window is missing.",
  history_unavailable: "Open-interest history is shorter than the window (warming up).",
  not_liquid: "The contract is below the liquidity gate.",
  kline_gap: "A 15-minute bar is missing inside the window.",
};

export function reasonText(code: string): string {
  return REASON_TEXT[code] ?? code;
}

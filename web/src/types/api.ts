// Mirrors backend/src/tss/api/schemas/models.py. Timestamps are ISO-8601 UTC strings.

export type WindowId = "1h" | "4h";

export interface AgentRun {
  agent: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  rows_in: number | null;
  rows_out: number | null;
  selected_count: number | null;
  error_component: string | null;
  error_message: string | null;
  meta: Record<string, unknown> | null;
}

export interface UniverseCounts {
  total: number;
  active: number;
  liquid: number;
  denylisted: number;
  zero_fee: number;
}

export interface StatusResponse {
  state: string;
  reason: string | null;
  state_updated_at: string | null;
  runs: AgentRun[];
  next_runs: Record<string, string | null>;
  universe: UniverseCounts;
  db_size_bytes: number;
  telegram_configured: boolean;
  now: string;
}

export interface DiscoveryRow {
  symbol: string;
  zero_fee: boolean | null;
  pinned: boolean;
  last_price: number | null;
  price_change_15m_pct: number | null;
  rvol_15m: number | null;
  fut_amount24: number | null;
  oi_notional_usdt: number | null;
  funding_rate: number | null;
  utc_day_change_pct: number | null;
  pool_rank: number | null;
  passed_gate2: boolean;
  selection_rank: number | null;
}

export interface DiscoveryResponse {
  cycle_id: string | null;
  ts: string | null;
  pool: DiscoveryRow[];
  pinned: DiscoveryRow[];
}

export interface ClassificationRow {
  symbol: string;
  window: WindowId;
  ts: string;
  pinned: boolean;
  last_price: number | null;
  price_change_15m_pct: number | null;
  price_change_pct: number | null;
  oi_notional_usdt: number | null;
  oi_change_pct: number | null;
  fut_volume_change_pct: number | null;
  spot_volume_change_pct: number | null;
  funding_now: number | null;
  funding_delta: number | null;
  state: string;
  flags: string[];
  unreliable_reasons: string[];
}

export interface ClassificationResponse {
  window: WindowId;
  cycle_id: string | null;
  ts: string | null;
  rows: ClassificationRow[];
}

export interface HistoryPoint {
  ts: string;
  state: string;
  price_change_pct: number | null;
  oi_change_pct: number | null;
  fut_volume_change_pct: number | null;
  spot_volume_change_pct: number | null;
  funding_now: number | null;
  funding_delta: number | null;
  flags: string[];
}

export interface HistoryResponse {
  symbol: string;
  window: WindowId;
  hours: number;
  points: HistoryPoint[];
}

export interface MoverRow {
  rank: number;
  symbol: string;
  day_open: number | null;
  last_price: number | null;
  change_pct: number | null;
  fut_amount24: number | null;
  oi_notional_usdt: number | null;
  funding_rate: number | null;
}

export interface MoversResponse {
  status: "OK" | "WAITING_DAY_OPEN" | "NO_DATA";
  ts: string | null;
  gainers: MoverRow[];
  losers: MoverRow[];
}

export interface ApiErrorBody {
  error: { code: string; message: string; component: string };
}

export interface NewsItem {
  id: number;
  source: string;
  title: string;
  url: string;
  published_at: string | null;
  fetched_at: string;
  symbols: string[];
}

export interface NewsResponse {
  symbol: string | null;
  items: NewsItem[];
}

export type SignalTimeframe = "5m" | "15m" | "1h";

export interface SignalRow {
  timeframe: SignalTimeframe;
  bar_close_time: string;
  m_trend: string;
  last_event: string;
  bars_ago: number | null;
  against_htf: boolean | null;
  htf_supertrend: string | null;
  local_supertrend: string;
  consolidated_trend: string;
  long_score: number;
  short_score: number;
  long_grade: string;
  short_grade: string;
  rsi_divergence: string | null;
  sr_letter: string | null;
  zone_position: string | null;
  price_vs_vwap: string | null;
  computed_at: string;
}

export interface SignalSymbol {
  symbol: string;
  pinned: boolean;
  selection_rank: number | null;
  rows: SignalRow[];
}

export interface SignalsResponse {
  updated_at: string | null;
  symbols: SignalSymbol[];
}

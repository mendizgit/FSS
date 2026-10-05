// WebSocket events (Arch §10): {type, ts, data}.

export interface TickerEvent {
  type: "ticker";
  ts: string;
  data: { symbol: string; last_price: number | null; fair_price: number | null };
}

export interface SimpleEvent {
  type:
    | "agent_status"
    | "cycle_complete"
    | "movers_updated"
    | "system_state"
    | "news_new"
    | "signal_new";
  ts: string;
  data: Record<string, unknown>;
}

export type TssEvent = TickerEvent | SimpleEvent;

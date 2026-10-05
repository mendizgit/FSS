import type { TickerEvent } from "@/types/events";

export interface LiveTick {
  price: number;
  previous: number | null;
  at: number;
}

// Live prices live outside React Query: ticks never trigger refetches (integration skill).
const ticks = new Map<string, LiveTick>();
const listeners = new Map<string, Set<() => void>>();

export function applyTick(event: TickerEvent): void {
  const { symbol, last_price: price } = event.data;
  if (price === null || !Number.isFinite(price)) return;
  const prev = ticks.get(symbol);
  if (prev && prev.price === price) return;
  ticks.set(symbol, { price, previous: prev?.price ?? null, at: Date.now() });
  listeners.get(symbol)?.forEach((l) => l());
}

export function subscribeTick(symbol: string, listener: () => void): () => void {
  let set = listeners.get(symbol);
  if (!set) {
    set = new Set();
    listeners.set(symbol, set);
  }
  set.add(listener);
  return () => {
    set.delete(listener);
  };
}

export function getTick(symbol: string): LiveTick | undefined {
  return ticks.get(symbol);
}
